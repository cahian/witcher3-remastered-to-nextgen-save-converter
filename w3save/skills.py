"""Bounded inspection of the observed tagged skill and progress serialization.

These functions accept full *decompressed* images and never read or write files.
Unknown states are not inferred to be compatible with the migration profile.
"""
import hashlib
import struct

from .metadata import parse_meta, require

SOURCE_VERSION = (66, 29, 164)
NATIVE_VERSION = (64, 27, 163)
CORE_SKILLS = frozenset(
    [f'S_{path}_{i}' for path in ('Sword', 'Magic', 'Alchemy') for i in range(1, 6)]
    + ['S_Perk_08']
)
MAX_ARRAY_COUNT = 4096


class Snapshot:
    """Inspect a validated image without changing its bytes."""

    def __init__(self, data):
        require(isinstance(data, (bytes, bytearray)), 'Snapshot requires bytes')
        self.data = bytes(data)
        self.vt, self.nm, self.rb, self.names, self.roots, self.entries = parse_meta(self.data)
        self.payload_end = min(self.nm, self.rb)
        self.version = struct.unpack_from('<III', self.data, 3088)
        self._names = {name: index for index, name in enumerate(self.names)}

    @classmethod
    def from_bytes(cls, data):
        return cls(data)

    def _name(self, index):
        require(0 <= index < len(self.names), 'Name index outside dictionary')
        return self.names[index]

    def scalar(self, type_name, value, depth=0):
        sizes = {'Int32': 4, 'Uint32': 4, 'Uint16': 2, 'Int16': 2,
                 'Uint8': 1, 'Int8': 1, 'Bool': 1}
        if type_name in sizes:
            require(len(value) == sizes[type_name], 'Invalid scalar length')
            return int.from_bytes(value, 'little', signed=type_name.startswith('Int'))
        if type_name == 'Float':
            require(len(value) == 4, 'Invalid float length')
            return struct.unpack('<f', value)[0]
        if type_name.startswith('E') or type_name == 'CName':
            require(len(value) == 2, 'Invalid enum/name length')
            return self._name(struct.unpack('<H', value)[0])
        if type_name in ('SItemUniqueId', 'SMutationProgress'):
            fields, end = self.read_struct(value, 0, len(value), depth+1)
            require(end == len(value), 'Trailing bytes in nested structure')
            return fields
        return value.hex()

    def read_struct(self, data, offset, limit=None, depth=0):
        """Read one tagged structure, enforcing the caller's property boundary."""
        if limit is None:
            limit = len(data)
        require(depth <= 8 and 0 <= offset < limit <= len(data), 'Invalid structure bounds')
        require(data[offset] == 0, 'Unsupported structure prefix')
        pos = offset+1
        fields = {}
        while True:
            require(pos+2 <= limit, 'Truncated structure field name')
            name = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            if name == 0:
                return fields, pos
            require(pos+6 <= limit, 'Truncated structure field header')
            type_idx, length = struct.unpack_from('<HI', data, pos)
            pos += 6
            require(length >= 4 and length-4 <= limit-pos, 'Field exceeds structure bounds')
            key, type_name = self._name(name), self._name(type_idx)
            require(key and type_name and key not in fields, 'Duplicate/empty structure field')
            fields[key] = self.scalar(type_name, data[pos:pos+length-4], depth)
            pos += length-4

    def arrays(self, name, struct_name, start=3100, end=None):
        """Return offset/count/values for every matching tagged struct array."""
        type_name = 'array:2,0,'+struct_name
        if name not in self._names or type_name not in self._names:
            return []
        if end is None:
            end = self.payload_end
        require(3100 <= start <= end <= self.payload_end, 'Invalid array search bounds')
        needle = struct.pack('<HH', self._names[name], self._names[type_name])
        results = []
        pos = start
        while True:
            offset = self.data.find(needle, pos, end)
            if offset < 0:
                return results
            pos = offset+1
            require(offset+12 <= end, 'Truncated array header')
            length, count = struct.unpack_from('<II', self.data, offset+4)
            boundary = offset+4+length
            require(length >= 8 and boundary <= end, 'Array exceeds search bounds')
            require(count <= MAX_ARRAY_COUNT and count*3 <= length-8, 'Invalid struct array count')
            cursor = offset+12
            values = []
            for _ in range(count):
                value, cursor = self.read_struct(self.data, cursor, boundary)
                values.append(value)
            require(cursor == boundary, 'Trailing bytes in struct array')
            results.append({'offset': offset, 'count': count, 'values': values})

    def wrappers(self, marker, name, type_name=None, start=3100, end=None):
        """Find typed native wrappers using their dictionary identities and sizes."""
        if end is None:
            end = self.payload_end
        if name not in self._names or type_name is not None and type_name not in self._names:
            return []
        needle = marker+struct.pack('<H', self._names[name])
        if type_name is not None:
            needle += struct.pack('<H', self._names[type_name])
        found = []
        pos = start
        while True:
            offset = self.data.find(needle, pos, end)
            if offset < 0:
                return found
            pos = offset+1
            header, size_at = (10, 6) if marker == b'BLCK' else (12, 8)
            require(offset+header <= end, 'Truncated serializer wrapper')
            size = struct.unpack_from('<I', self.data, offset+size_at)[0]
            require(size <= end-offset-header, 'Serializer wrapper exceeds owner')
            found.append({'offset': offset, 'start': offset+header, 'end': offset+header+size})

    def skill_owners(self):
        """Associate skills with their containing SXAP entity, never array order.

        Ciri is identified by its observed ``ciri_player``/``ciri_winter`` typed
        appearance and a separate typed ``player`` identity marker. Geralt
        additionally needs a saved W3LevelManager on the same entity. Merely
        containing the text 'Ciri' somewhere in a save is not identification.
        """
        result = []
        serial = [(off, size) for off, size in self.entries
                  if self.data[off:off+2] == b'SS' and self.data[off+6:off+10] == b'SXAP']
        for skills in self.arrays('skills', 'SSkill'):
            offset = skills['offset']
            bounds = [(off, size) for off, size in serial if off <= offset < off+size]
            require(bounds, 'Skills do not belong to an identified serialized owner')
            off, size = min(bounds, key=lambda pair: pair[1])
            require(size >= 22 and struct.unpack_from('<I', self.data, off+2)[0] == size-6,
                    'Invalid serialized owner length')
            ability = self.wrappers(b'PORP', 'abilityManager', 'handle:W3AbilityManager', off, off+size)
            require(len(ability) == 1 and ability[0]['start'] <= offset < ability[0]['end'],
                    'Skills are outside a unique ability manager')
            appearances = self.wrappers(b'AVAL', 'appearance', 'CName', off, off+size)
            actors = self.wrappers(b'AVAL','a','CName',off,off+size)
            is_player = any(a['end']-a['start'] == 2 and self.scalar('CName',self.data[a['start']:a['end']]) == 'player'
                            for a in actors)
            is_ciri = is_player and any(a['end']-a['start'] == 2 and self.scalar('CName',self.data[a['start']:a['end']]) in ('ciri_player','ciri_winter')
                                       for a in appearances)
            levels = self.wrappers(b'PORP','levelManager','handle:W3LevelManager',off,off+size)
            role = 'ciri' if is_ciri else 'geralt' if is_player and len(levels) == 1 else 'unknown'
            result.append({'role':role,'offset':off,'end':off+size,'skills':skills,
                           'ability':ability[0],'version':struct.unpack_from('<III',self.data,off+10)})
        return result

    def owner_for_role(self, role):
        matches = [owner for owner in self.skill_owners() if owner['role'] == role]
        require(len(matches) == 1, f'Expected exactly one {role} skill owner; found {len(matches)}')
        return matches[0]

    def manager_fields(self, owner):
        wrapper = owner['ability']
        start, end = wrapper['start'], wrapper['end']
        require(end-start >= 11 and self.data[start:start+2] == b'\0\1', 'Unsupported ability handle')
        require(self._name(struct.unpack_from('<H',self.data,start+6)[0]) == 'W3PlayerAbilityManager',
                'Unsupported ability manager class')
        fields, finish = self.read_struct(self.data,start+8,end)
        require(finish == end,'Trailing bytes in ability manager')
        return fields

    def facts(self):
        roots = [off for idx,off in self.roots if self.names[idx] == 'facts']
        if not roots:
            return {}
        require(len(roots) == 1,'Ambiguous fact root')
        root = roots[0]
        sizes = [size for off,size in self.entries if off == root]
        require(len(sizes) == 1,'Ambiguous fact root size')
        end = root+sizes[0]
        require(root+34 <= end and self.data[root+26:root+30] == b'SBDF','Unsupported fact serialization')
        declared = struct.unpack_from('<H',self.data,root+30)[0]
        pos = root+34
        result = {}
        while pos < end and self.data[pos:pos+4] != b'EBDF':
            first = self.data[pos]
            pos += 1
            length, shift = first & 63, 6
            if first & 64:
                while True:
                    require(pos < end and shift <= 27,'Invalid compact fact string length')
                    byte = self.data[pos]
                    pos += 1
                    length |= (byte & 127) << shift
                    shift += 7
                    if not byte & 128:
                        break
            if pos < end and self.data[pos] == 1:
                pos += 1
            width = 1 if first & 128 else 2
            require(0 < length <= 65535 and length*width <= end-pos,'Invalid fact name length')
            try:
                name = self.data[pos:pos+length*width].decode('utf-8' if width == 1 else 'utf-16-le')
            except UnicodeDecodeError as exc:
                raise ValueError('Invalid fact name encoding') from exc
            pos += length*width
            require(pos+4 <= end,'Truncated fact header')
            flag,count = struct.unpack_from('<HH',self.data,pos)
            pos += 4
            require(count*10 <= end-pos,'Truncated fact values')
            values = []
            for _ in range(count):
                value,created,expires = struct.unpack_from('<hff',self.data,pos)
                pos += 10
                values.append({'value':value,'created':created,'expires':expires})
            require(name not in result,'Duplicate fact name')
            result[name] = {'flag':flag,'total':sum(v['value'] for v in values),'entries':values}
        require(pos+4 == end and self.data[pos:pos+4] == b'EBDF' and len(result) == declared,
                'Fact count or end marker mismatch')
        return result

    def summary(self):
        owners = self.skill_owners()
        return {
            'version': self.version,
            'decoded_sha256': hashlib.sha256(self.data).hexdigest(),
            'skills': [{'offset':o['skills']['offset'],'owner':o['role'],'count':o['skills']['count'],
                        'learned':[v for v in o['skills']['values'] if v.get('level',0)>0],
                        'purchased':[v for v in o['skills']['values'] if v.get('level',0)>0 and not v.get('isCoreSkill')]}
                       for o in owners],
            'skillSlots':self.arrays('skillSlots','SSkillSlot'),
            'points':self.arrays('points','SSpendablePoints'),
            'mutagenSlots':self.arrays('mutagenSlots','SMutagenSlot'),
        }


def _single_owner_array(snapshot,owner,name,type_name):
    arrays = snapshot.arrays(name,type_name,owner['offset'],owner['end'])
    require(len(arrays) == 1,f'Expected one {name} array on {owner["role"]}')
    return arrays[0]['values']


def check_unspent_core_state(values):
    """Reject learned non-core skills or altered core identities/levels."""
    require(all(isinstance(v.get('level',0),int) and v.get('level',0) >= 0 for v in values),
            'Negative or malformed skill level')
    named = [v.get('skillType') for v in values if v]
    require(None not in named and len(named) == len(set(named)), 'Duplicate or missing skill identities')
    require(all(not v.get('level',0) or v.get('isCoreSkill') for v in values),
            'Ciri has purchased skills; this state is unsupported')
    cores = {v['skillType']:v for v in values if v.get('isCoreSkill')}
    require(set(cores) == CORE_SKILLS and all(v.get('level') == 1 for v in cores.values()),
            'Core skill state differs from the supported profile')
    return cores


def check_migration_profile(raw):
    """Return the supported early-game profile, or raise ValueError.

    This is intentionally narrower than identifying a Remastered save: three
    named level-one skills, one free point, no mutation research and unspent Ciri.
    """
    snapshot = Snapshot.from_bytes(raw)
    require(snapshot.version == SOURCE_VERSION,'Unsupported source version; expected 66/29/164')
    owners = snapshot.skill_owners()
    require(len(owners) == 2,'Unsupported number of player skill managers')
    geralt,ciri = snapshot.owner_for_role('geralt'),snapshot.owner_for_role('ciri')
    require(all(o['version'] == SOURCE_VERSION and o['skills']['count'] == 167 for o in owners),
            'Unsupported source player serializer/skill count')
    check_unspent_core_state(ciri['skills']['values'])
    skills = geralt['skills']['values']
    purchased = [v for v in skills if v.get('level',0)>0 and not v.get('isCoreSkill')]
    expected = ['sword_s22','sword_s23','sword_s24']
    require(sorted(v.get('abilityName','') for v in purchased) == expected,
            'Unsupported purchased skills')
    require(all(v.get('level') == 1 and v.get('cost') == 1 and not v.get('isTemporary')
                and v.get('skillType') == 'S_'+v['abilityName'][0].upper()+v['abilityName'][1:] for v in purchased),
            'Unsupported purchased skill level/cost/type')
    check_unspent_core_state([v for v in skills if v not in purchased])
    points = _single_owner_array(snapshot,geralt,'points','SSpendablePoints')
    require(len(points) == 2 and points[0].get('free',0) == 1 and points[0].get('used',0) == 3,
            'Expected one free and three used skill points')
    for owner in owners:
        snapshot.manager_fields(owner)
        slots = _single_owner_array(snapshot,owner,'mutagenSlots','SMutagenSlot')
        require(len(slots) == 4 and all(v.get('skillGroupID') == i and v.get('equipmentSlot') == f'EES_SkillMutagen{i}'
                                      for i,v in enumerate(slots,1)), 'Unsupported mutagen slot layout')
        bonuses = _single_owner_array(snapshot,owner,'mutagenBonuses','SMutagenBonusAlchemy19')
        require(len(bonuses) == 9 and all(not v.get('count') and not v.get('abilityName') for v in bonuses),
                'Active mutagen synergy bonuses are unsupported')
        mutations = _single_owner_array(snapshot,owner,'mutations','SMutation')
        require(len(mutations) == 13,'Unsupported mutation definitions')
        for mutation in mutations:
            progress = mutation.get('progress',{})
            require(isinstance(progress,dict) and all(progress.get(k,0) == 0 for k in ('skillpointsUsed','redUsed','blueUsed','greenUsed'))
                    and progress.get('overallProgress',-1) <= 0,'Researched mutations are unsupported')
    return {'profile':'early-game-three-sword-skills','source_version':list(SOURCE_VERSION),
            'skill_points':{'free':1,'used':3,'total':4},'purchased_abilities':expected,
            'geralt_skill_count':167,'ciri_skill_count':167,'advanced_mutations':False}
