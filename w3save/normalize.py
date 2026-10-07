"""Normalize inactive Ciri using caller-supplied native Ciri definitions.

This is a pure byte transformation. It does not transplant Geralt state, change
quests, or claim that a successful structural check is an in-game load test.
"""
from collections import Counter
import hashlib
import struct

from .metadata import parse_meta, require
from .skills import Snapshot, NATIVE_VERSION, check_unspent_core_state


def _validate_native_order(values):
    """Validate serialized enum positions; a count of 102 alone is insufficient."""
    names = (['S_SUndefined'] +
             [f'S_{path}_{i}' for path in ('Sword','Magic','Alchemy') for i in range(1,6)] +
             [f'S_Sword_s{i:02}' if i != 14 else 'S_UNUSED1' for i in range(1,22)] +
             [f'S_Magic_s{i:02}' for i in range(1,21)] + ['S_UNUSED2'] +
             [f'S_Alchemy_s{i:02}' for i in range(1,21)] + ['S_Skill_MAX','S_Perk_MIN'] +
             [f'S_Perk_{i:02}' for i in range(1,23)])
    require(len(values) == len(names) == 102,'Invalid native skills size')
    require(all(not value or value.get('skillType') == names[i] for i,value in enumerate(values)),
            'Skill identities do not follow the native 4.04 enum order')


def _validate_migrated_geralt(target):
    """Finalization must follow the in-game Geralt migration and native save."""
    geralt = target.owner_for_role('geralt')
    target.manager_fields(geralt)
    require(geralt['version'] == NATIVE_VERSION and geralt['skills']['count'] == 102,
            'Geralt must already have a native 102-entry skill array; complete the in-game migration first')
    _validate_native_order(geralt['skills']['values'])
    try:
        check_unspent_core_state(geralt['skills']['values'])
    except ValueError as exc:
        raise ValueError('Geralt does not match the migrated core-only skill profile') from exc
    points = target.arrays('points','SSpendablePoints',geralt['offset'],geralt['end'])
    require(len(points) == 1 and points[0]['count'] == 2,
            'Geralt must have one recognized skill/experience points array')
    skill_points = points[0]['values'][0]
    require(skill_points.get('free',0) == 4 and skill_points.get('used',0) == 0,
            'Geralt must have four free and zero used skill points after migration')


def _translate_skills(source, source_array, target):
    """Translate every dictionary reference in the observed SSkill layout."""
    target_names = {name:i for i,name in enumerate(target.names)}
    def translate(index):
        require(0 <= index < len(source.names),'Reference name index outside dictionary')
        name = source.names[index]
        require(name in target_names,f'Target dictionary lacks reference name: {name}')
        return target_names[name]
    pos = source_array['offset']+12
    boundary = source_array['offset']+4+struct.unpack_from('<I',source.data,source_array['offset']+4)[0]
    records = []
    types = Counter()
    for _ in range(102):
        require(pos < boundary and source.data[pos] == 0,'Unsupported reference skill structure')
        pos += 1
        record = bytearray(b'\0')
        while True:
            require(pos+2 <= boundary,'Truncated reference skill field')
            ni = struct.unpack_from('<H',source.data,pos)[0]
            pos += 2
            if not ni:
                record += b'\0\0'
                break
            require(pos+6 <= boundary,'Truncated reference skill header')
            ti,length = struct.unpack_from('<HI',source.data,pos)
            pos += 6
            require(length >= 4 and length-4 <= boundary-pos,'Reference field exceeds array')
            value = source.data[pos:pos+length-4]
            pos += length-4
            typ = source._name(ti)
            types[typ] += 1
            if typ.startswith('E') or typ == 'CName':
                require(len(value) == 2,'Unsupported name/enum field length')
                value = struct.pack('<H',translate(struct.unpack('<H',value)[0]))
            elif typ in ('array:2,0,CName','array:2,0,ESkill'):
                require(len(value) >= 4,'Truncated name/enum array')
                count = struct.unpack_from('<I',value)[0]
                require(count <= 4096 and len(value) == 4+count*2,'Unsupported name/enum array length')
                indexes = struct.unpack_from('<'+'H'*count,value,4)
                value = value[:4]+struct.pack('<'+'H'*count,*(translate(i)for i in indexes))
            else:
                require(typ in ('Int32','String','Bool'),'Unsupported reference skill field type: '+typ)
            record += struct.pack('<HHI',translate(ni),translate(ti),length)+value
        records.append(record)
    require(pos == boundary,'Trailing reference skill bytes')
    body = struct.pack('<I',102)+b''.join(records)
    prop = struct.pack('<HHI',target_names['skills'],target_names['array:2,0,SSkill'],len(body)+4)+body
    return prop,dict(types)


def _splice_property(data,lo,hi,replacement):
    """Relocate one opaque property and verify every surviving byte.

    No pointer may address its interior. Only recognized enclosing serializer
    sizes and the global root/variable tables are updated.
    """
    vt,nm,rb,names,roots,entries = parse_meta(data)
    require(3100 <= lo < hi <= min(nm,rb),'Replacement outside save payload')
    delta = len(replacement)-(hi-lo)
    def shift(position):
        require(not lo < position < hi,'Pointer targets replaced property interior')
        return position+delta if position >= hi else position
    def change(start,end):
        return shift(end)-shift(start)-(end-start)
    patches = {}
    kinds = Counter()
    def patch(offset,old,new,kind):
        require(0 <= offset <= len(data)-4 and struct.unpack_from('<I',data,offset)[0] == old,
                'Relocation old value mismatch')
        require(not lo <= offset < hi and 0 <= new <= 0xffffffff,'Invalid relocation value')
        if offset in patches:
            require(patches[offset] == new,'Conflicting relocation patches')
        elif new != old:
            patches[offset] = new
            kinds[kind] += 1
    affected = []
    for off,size in entries:
        diff = change(off,off+size)
        if diff:
            tag = data[off:off+2]
            require(tag in (b'BS',b'SS'),'Unknown enclosing variable type')
            affected.append([off,size,tag.decode(),diff])
            if tag == b'SS':
                require(struct.unpack_from('<I',data,off+2)[0] == size-6,'Serialized size mismatch')
                patch(off+2,size-6,size-6+diff,'SS_size')
    wrappers = []
    for marker,header,size_at in ((b'BLCK',10,6),(b'AVAL',12,8),(b'PORP',12,8),(b'ROTS',8,4)):
        pos = 0
        while True:
            pos = data.find(marker,pos,min(nm,rb))
            if pos < 0:
                break
            off = pos
            pos += 1
            if lo <= off < hi or off+header > min(nm,rb):
                continue
            length = struct.unpack_from('<I',data,off+size_at)[0]
            end = off+header+length
            if not length or end > min(nm,rb):
                continue
            if marker == b'ROTS':
                if data[end:end+4] != b'STOR':
                    continue
            else:
                ni = struct.unpack_from('<H',data,off+4)[0]
                if not 0 < ni < len(names):
                    continue
                if marker != b'BLCK':
                    ti = struct.unpack_from('<H',data,off+6)[0]
                    if not 0 < ti < len(names):
                        continue
            if off+header <= lo and hi <= end:
                diff = change(off+header,end)
                patch(off+size_at,length,length+diff,marker.decode()+'_size')
                wrappers.append([marker.decode(),off,length,diff])
    require(kinds == {'SS_size':1,'BLCK_size':1,'PORP_size':1},'Unsupported enclosing Ciri layout')
    for i,(_,off) in enumerate(roots):
        patch(rb+6+6*i+2,off,shift(off),'root_offset')
    for i,(off,size) in enumerate(entries):
        patch(vt+4+8*i,off,shift(off),'variable_offset')
        patch(vt+4+8*i+4,size,size+change(off,off+size),'variable_size')
    patch(vt-10,nm,shift(nm),'NM_pointer')
    patch(vt-6,rb,shift(rb),'RB_pointer')
    patch(len(data)-6,vt,shift(vt),'SC_pointer')
    result = bytearray(data[:lo]+replacement+data[hi:])
    for off,value in patches.items():
        struct.pack_into('<I',result,shift(off),value)
    new_vt,new_nm,new_rb,new_names,new_roots,new_entries = parse_meta(result)
    require(new_names == names and len(result) == len(data)+delta,'Relocated metadata mismatch')
    require((new_vt,new_nm,new_rb) == tuple(map(shift,(vt,nm,rb))),'Relocated table pointers mismatch')
    require(new_roots == [(idx,shift(off))for idx,off in roots],'Relocated root mismatch')
    require(new_entries == [(shift(off),size+change(off,off+size))for off,size in entries],
            'Relocated variable mismatch')
    for (off,size),(new_off,new_size) in zip(entries,new_entries):
        if size == new_size:
            require(result[new_off:new_off+new_size] == data[off:off+size],
                    'Unrelated variable bytes changed')
    restored = bytearray(result)
    for off in patches:
        restored[shift(off):shift(off)+4] = data[off:off+4]
    require(restored[:lo] == data[:lo] and restored[lo+len(replacement):] == data[hi:],
            'Bytes outside the skill property and relocation fields changed')
    return bytes(result),{'delta_bytes':delta,'replaced_range':[lo,hi],
                          'affected_entries':affected,'wrappers':wrappers,
                          'patch_counts':dict(kinds),'global_entries':len(entries),
                          'root_entries':len(roots)}


def normalize_ciri(target_raw,reference_raw):
    """Return (new full image, report), changing only a verified Ciri property.

    Both inputs must be native 64/27/163 images. A unique, semantically identified
    Ciri player is required in each. Ciri must have no purchased skills and retain the observed
    sixteen level-one core skills. Geralt must already have the migrated native
    102-entry core-only skill array and four free/zero used points. A 102-entry
    Ciri target is an unchanged no-op only after these checks.
    """
    target,reference = Snapshot.from_bytes(target_raw),Snapshot.from_bytes(reference_raw)
    require(target.version == NATIVE_VERSION and reference.version == NATIVE_VERSION,
            'Target and reference must both be native 64/27/163 saves')
    _validate_migrated_geralt(target)
    owner,ref_owner = target.owner_for_role('ciri'),reference.owner_for_role('ciri')
    target.manager_fields(owner)
    reference.manager_fields(ref_owner)
    require(owner['version'] == NATIVE_VERSION,'Target Ciri serializer must be native 64/27/163')
    # A native 4.04 expansion-start save carries this inactive Ciri cache from
    # the shipped legacy template. Its global header is still required above.
    require(ref_owner['version'] in (NATIVE_VERSION,(57,10,162)),
            'Unsupported reference Ciri serializer version')
    original,ref_array = owner['skills'],ref_owner['skills']
    require(original['count'] in (102,167),'Unsupported target Ciri skill count')
    require(ref_array['count'] == 102,'Reference Ciri must have 102 native skill entries')
    _validate_native_order(ref_array['values'])
    target_core = check_unspent_core_state(original['values'])
    ref_core = check_unspent_core_state(ref_array['values'])
    require({k:(v.get('level'),v.get('isCoreSkill'))for k,v in target_core.items()} ==
            {k:(v.get('level'),v.get('isCoreSkill'))for k,v in ref_core.items()},
            'Target/reference Ciri core states differ')
    report = {'changed':False,'owner':'ciri','before_count':original['count'],'after_count':102,
              'input_sha256':hashlib.sha256(target.data).hexdigest(),
              'reference_sha256':hashlib.sha256(reference.data).hexdigest(),
              'levels_and_core_flags_preserved':True,'in_game_validation':False,
              'geralt_migration_profile_verified':True,
              'reference_ciri_serializer':list(ref_owner['version'])}
    if original['count'] == 102:
        _validate_native_order(original['values'])
        report.update({'reason':'Ciri already has 102 native entries','output_sha256':report['input_sha256']})
        return target.data,report
    replacement,types = _translate_skills(reference,ref_array,target)
    lo = original['offset']
    hi = lo+4+struct.unpack_from('<I',target.data,lo+4)[0]
    result,relocation = _splice_property(target.data,lo,hi,replacement)
    updated = Snapshot.from_bytes(result)
    normalized = updated.owner_for_role('ciri')['skills']
    require(normalized['count'] == 102,'Normalized Ciri count mismatch')
    check_unspent_core_state(normalized['values'])
    report.update({'changed':True,'output_sha256':hashlib.sha256(result).hexdigest(),
                   'relocation':relocation,'remapped_field_types':types,
                   'all_bytes_outside_property_and_relocation_unchanged':True})
    return result,report
