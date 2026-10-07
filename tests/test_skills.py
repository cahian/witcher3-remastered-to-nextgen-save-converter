"""Hand-built synthetic saves: no game assets or personal checkpoints."""
import importlib
import struct
import unittest


CORE = [f'S_{path}_{i}' for path in ('Sword', 'Magic', 'Alchemy') for i in range(1, 6)] + ['S_Perk_08']


def synthetic_save(*, ciri_count=167, version=(64, 27, 163), reverse_names=False,
                   ciri_first=False, ciri_level=1, ciri_spent=False,
                   identity=True, source=False, advanced=False, free=None, used=None,
                   bad_core=False, duplicate_ciri=False, winter=False, player=True,
                   ciri_serializer=None, scrambled_native=False, geralt_serializer=None,
                   scrambled_geralt=False, geralt_purchased=False, duplicate_geralt=False):
    """Construct opaque owners around typed properties and explicit metadata."""
    names = ['Entity', 'abilityManager', 'handle:W3AbilityManager',
             'W3PlayerAbilityManager', 'skills', 'array:2,0,SSkill',
             'skillType', 'ESkill', 'level', 'Int32', 'cost', 'maxLevel',
             'abilityName', 'CName', 'isCoreSkill', 'Bool', 'String',
             'appearance', 'ciri_player', 'ciri_winter', 'geralt_player', 'a', 'player', 'levelManager',
             'handle:W3LevelManager', 'points', 'array:2,0,SSpendablePoints',
             'free', 'used', 'mutagenSlots', 'array:2,0,SMutagenSlot',
             'skillGroupID', 'equipmentSlot', 'EEquipmentSlots',
             'mutagenBonuses', 'array:2,0,SMutagenBonusAlchemy19',
             'mutations', 'array:2,0,SMutation', 'progress', 'SMutationProgress',
             'skillpointsUsed', 'overallProgress', 'isTemporary', 'facts',
             'modifierTags', 'array:2,0,CName', 'synthetic_modifier']
    names += CORE + [s.lower() for s in CORE]
    names += [f'S_Sword_s{i}' for i in (22, 23, 24)]
    names += [f'sword_s{i}' for i in (22, 23, 24)]
    names += ['S_Sword_s01','sword_s01']
    names += [f'EES_SkillMutagen{i}' for i in range(1, 5)]
    if reverse_names:
        names.reverse()
    idx = {n: i+1 for i, n in enumerate(names)}
    def prop(n, t, value):
        return struct.pack('<HHI', idx[n], idx[t], len(value)+4)+value
    def scalar(n, t, value):
        if t in ('CName', 'ESkill', 'EEquipmentSlots'):
            raw = struct.pack('<H', idx[value])
        elif t == 'Bool':
            raw = bytes([value])
        else:
            raw = struct.pack('<i', value)
        return prop(n, t, raw)
    def record(fields):
        return b'\0'+b''.join(fields)+b'\0\0'
    def array(n, t, records):
        return prop(n, 'array:2,0,'+t, struct.pack('<I', len(records))+b''.join(records))
    def wrapper(tag, n, t, value):
        return tag+struct.pack('<HHI', idx[n], idx[t], len(value))+value
    def owner(ciri):
        count = ciri_count if ciri else (167 if source else 102)
        records = [record([])]*count
        for core_index,n in enumerate(CORE,1):
            fields = [scalar('skillType','ESkill',n), scalar('level','Int32',ciri_level if ciri else 1),
                      scalar('abilityName','CName',n.lower()), scalar('cost','Int32',1),
                      scalar('maxLevel','Int32',1), scalar('isCoreSkill','Bool',0 if bad_core and ciri and n == CORE[0] else 1)]
            if n == CORE[0]:
                fields += [prop('modifierTags','array:2,0,CName',struct.pack('<IH',1,idx['synthetic_modifier']))]
            position = core_index if core_index < 16 else 130 if count == 167 else 87
            records[position] = record(fields)
        if source and not ciri or ciri_spent and ciri:
            for i in (22,23,24):
                records[i+15] = record([scalar('skillType','ESkill',f'S_Sword_s{i}'),
                                        scalar('abilityName','CName',f'sword_s{i}'),
                                        scalar('level','Int32',1), scalar('cost','Int32',1)])
        if ciri and scrambled_native:
            records[1],records[2] = records[2],records[1]
        if not ciri and scrambled_geralt:
            records[1],records[2] = records[2],records[1]
        if not ciri and geralt_purchased:
            records[16] = record([scalar('skillType','ESkill','S_Sword_s01'),
                                  scalar('abilityName','CName','sword_s01'),
                                  scalar('level','Int32',1),scalar('cost','Int32',1)])
        fields = [array('skills','SSkill',records)]
        slots = [record([scalar('skillGroupID','Int32',i),scalar('equipmentSlot','EEquipmentSlots',f'EES_SkillMutagen{i}')])for i in range(1,5)]
        fields += [array('mutagenSlots','SMutagenSlot',slots)]
        fields += [array('mutagenBonuses','SMutagenBonusAlchemy19',[record([])]*9)]
        mutation = record([prop('progress','SMutationProgress',record([
            scalar('skillpointsUsed','Int32',1 if advanced else 0),scalar('overallProgress','Int32',-1)]))])
        fields += [array('mutations','SMutation',[mutation]*13)]
        payload = b'\0\1'+struct.pack('<I',0)+struct.pack('<H',idx['W3PlayerAbilityManager'])+record(fields)
        entity = wrapper(b'PORP','abilityManager','handle:W3AbilityManager',payload)
        if ciri and identity:
            entity += wrapper(b'AVAL','appearance','CName',struct.pack('<H',idx['ciri_winter' if winter else 'ciri_player']))
        if player:
            entity += wrapper(b'AVAL','a','CName',struct.pack('<H',idx['player']))
        if not ciri:
            free_points = (1 if source else 4) if free is None else free
            used_points = (3 if source else 0) if used is None else used
            point_data = array('points','SSpendablePoints',[record([scalar('free','Int32',free_points),scalar('used','Int32',used_points)]),record([])])
            entity += wrapper(b'PORP','levelManager','handle:W3LevelManager',point_data)
        entity += b'opaque-ciri-state' if ciri else b'opaque-geralt-state'
        serializer = ciri_serializer if ciri and ciri_serializer is not None else version
        if not ciri and geralt_serializer is not None:
            serializer = geralt_serializer
        body = b'SXAP'+struct.pack('<III',*serializer)+b'BLCK'+struct.pack('<HI',idx['Entity'],len(entity))+entity
        return b'SS'+struct.pack('<I',len(body))+body
    owners = [owner(True),owner(False)] if ciri_first else [owner(False),owner(True)]
    if duplicate_ciri:
        owners.append(owner(True))
    if duplicate_geralt:
        owners.append(owner(False))
    data = bytearray(b'SNFHFZLC'+bytes(3084-8)+b'SAV3'+struct.pack('<III',*version))
    entries = []
    for block in owners:
        entries.append((len(data),len(block)))
        data += block
    # An independent root verifies relocation after the replaced Ciri property.
    fact_root = len(data)
    fact_bytes = b'BS'+bytes(24)+b'SBDF'+struct.pack('<HH',1,0)+b'\x87q1_done'+struct.pack('<HHhff',0,1,1,2.0,-1.0)+b'EBDF'
    data += fact_bytes
    entries.append((fact_root,len(fact_bytes)))
    nm = len(data)
    data += b'NMMANU'+struct.pack('<II',len(names),0)
    for n in names:
        raw=n.encode();data += bytes([len(raw)])+raw
    rb=len(data)
    data += b'RB'+struct.pack('<I',1)+struct.pack('<HI',idx['facts'],fact_root)
    data += struct.pack('<II',nm,rb)+b'SC'
    vt=len(data)
    data += struct.pack('<I',len(entries))+b''.join(struct.pack('<II',*e)for e in entries)
    data += struct.pack('<I',vt)+b'SE'
    return bytes(data)


class SkillsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('w3save.skills'), 'skills parser is not implemented')
        self.assertIsNotNone(importlib.util.find_spec('w3save.normalize'), 'Ciri normalization is not implemented')
        self.skills = importlib.import_module('w3save.skills')
        self.normalize = importlib.import_module('w3save.normalize').normalize_ciri

    def test_ciri_first_is_identified_and_geralt_preserved_with_reference_name_remap(self):
        target=synthetic_save(ciri_first=True)
        reference=synthetic_save(ciri_count=102,reverse_names=True)
        result,report=self.normalize(target,reference)
        snapshot=self.skills.Snapshot.from_bytes(result)
        counts={s['owner']:s['count']for s in snapshot.summary()['skills']}
        self.assertEqual(counts,{'ciri':102,'geralt':102})
        self.assertTrue(report['changed'])
        self.assertIn(b'opaque-ciri-state',result)
        self.assertIn(b'opaque-geralt-state',result)
        self.assertEqual(snapshot.facts()['q1_done']['total'],1)
        before=self.skills.Snapshot.from_bytes(target)
        old_geralt=before.owner_for_role('geralt')
        new_geralt=snapshot.owner_for_role('geralt')
        self.assertEqual(target[old_geralt['offset']:old_geralt['end']],result[new_geralt['offset']:new_geralt['end']])
        ciri=snapshot.owner_for_role('ciri')['skills']['values']
        self.assertEqual(ciri[1]['skillType'],'S_Sword_1')
        self.assertEqual(ciri[1]['level'],1)
        self.assertEqual(ciri[1]['isCoreSkill'],1)
        raw=bytes.fromhex(ciri[1]['modifierTags'])
        self.assertEqual(snapshot.names[struct.unpack_from('<H',raw,4)[0]],'synthetic_modifier')

    def test_already_native_ciri_is_byte_identical_noop(self):
        raw=synthetic_save(ciri_count=102)
        result,report=self.normalize(raw,synthetic_save(ciri_count=102,reverse_names=True))
        self.assertEqual(result,raw)
        self.assertFalse(report['changed'])

    def test_native_winter_reference_is_ciri_but_nonplayer_appearance_is_not(self):
        reference=synthetic_save(ciri_count=102,winter=True)
        result,report=self.normalize(synthetic_save(),reference)
        self.assertEqual(self.skills.Snapshot.from_bytes(result).owner_for_role('ciri')['skills']['count'],102)
        self.assertTrue(report['changed'])
        with self.assertRaises(ValueError):
            self.normalize(synthetic_save(player=False),reference)

    def test_known_legacy_ciri_cache_inside_native_reference_is_supported(self):
        reference=synthetic_save(ciri_count=102,winter=True,ciri_serializer=(57,10,162))
        result,report=self.normalize(synthetic_save(),reference)
        self.assertEqual(self.skills.Snapshot.from_bytes(result).owner_for_role('ciri')['skills']['count'],102)
        self.assertEqual(report['reference_ciri_serializer'],[57,10,162])
        with self.assertRaises(ValueError):
            self.normalize(synthetic_save(),synthetic_save(ciri_count=102,ciri_serializer=(65,28,164)))
        with self.assertRaises(ValueError):
            self.normalize(synthetic_save(ciri_serializer=(57,10,162)),reference)

    def test_native_sized_but_wrongly_ordered_skills_are_not_trusted(self):
        with self.assertRaises(ValueError):
            self.normalize(synthetic_save(),synthetic_save(ciri_count=102,scrambled_native=True))
        with self.assertRaises(ValueError):
            self.normalize(synthetic_save(ciri_count=102,scrambled_native=True),synthetic_save(ciri_count=102))

    def test_header_rewritten_candidate_cannot_skip_geralt_migration(self):
        ref=synthetic_save(ciri_count=102)
        for ciri_count in (167,102):
            with self.subTest(ciri_count=ciri_count),self.assertRaises(ValueError):
                self.normalize(synthetic_save(source=True,ciri_count=ciri_count),ref)

    def test_finalization_requires_migrated_geralt_points_and_unspent_native_skills(self):
        reference=synthetic_save(ciri_count=102,free=42,used=7)
        cases=[{'free':1},{'used':1},{'scrambled_geralt':True},{'geralt_purchased':True},
               {'geralt_serializer':(66,29,164)},{'duplicate_geralt':True}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.normalize(synthetic_save(**kwargs),reference)
        result,report=self.normalize(synthetic_save(),reference)
        self.assertTrue(report['changed'])
        self.assertEqual(self.skills.Snapshot.from_bytes(result).owner_for_role('geralt')['skills']['count'],102)

    def test_wrong_manager_class_is_rejected_for_target_players_and_reference_ciri(self):
        target=synthetic_save()
        reference=synthetic_save(ciri_count=102)
        for which,role in [('target','geralt'),('target','ciri'),('reference','ciri')]:
            raw=target if which == 'target' else reference
            snapshot=self.skills.Snapshot.from_bytes(raw)
            owner=snapshot.owner_for_role(role)
            corrupted=bytearray(raw)
            struct.pack_into('<H',corrupted,owner['ability']['start']+6,snapshot.names.index('CName'))
            bad_target,bad_reference=(bytes(corrupted),reference) if which == 'target' else (target,bytes(corrupted))
            with self.subTest(which=which,role=role),self.assertRaises(ValueError):
                self.normalize(bad_target,bad_reference)

    def test_rejects_unsupported_state_and_ambiguous_owners(self):
        ref=synthetic_save(ciri_count=102)
        cases=[{'version':(66,29,164)},{'ciri_spent':True},{'ciri_level':2},
               {'identity':False},{'bad_core':True},{'duplicate_ciri':True},{'ciri_count':166}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.normalize(synthetic_save(**kwargs),ref)
        with self.assertRaises(ValueError):
            self.normalize(synthetic_save(),synthetic_save(ciri_count=167))

    def test_truncated_struct_does_not_read_past_property(self):
        raw=synthetic_save()
        s=self.skills.Snapshot.from_bytes(raw)
        prop=s.arrays('skills','SSkill')[0]['offset']
        broken=bytearray(raw)
        struct.pack_into('<I',broken,prop+8,1000000000)
        with self.assertRaises(ValueError):
            self.skills.Snapshot.from_bytes(bytes(broken)).arrays('skills','SSkill')

    def test_source_profile_accepts_only_exact_points_and_unresearched_mutations(self):
        good=synthetic_save(source=True,version=(66,29,164))
        profile=self.skills.check_migration_profile(good)
        self.assertEqual(profile['skill_points'],{'free':1,'used':3,'total':4})
        self.assertEqual(profile['purchased_abilities'],['sword_s22','sword_s23','sword_s24'])
        for options in ({'free':2},{'advanced':True},{'ciri_spent':True}):
            with self.subTest(options=options),self.assertRaises(ValueError):
                self.skills.check_migration_profile(synthetic_save(source=True,version=(66,29,164),**options))


if __name__=='__main__':
    unittest.main()
