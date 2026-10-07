	// Candidate for the supplied checkpoint only. Requires in-game verification.
	// Call after super.Init(), before InitSkillSlots(), only for a restored 167-slot save.
	private final function MigrateInspectedRemasterCheckpoint() : bool
	{
		var i, used, free, learnedPoints : int;
		var witcher : W3PlayerWitcher;
		var skillDefs, removedNames : array<name>;
		var rebuiltSkills : array<SSkill>;
		var keptMutagens : array<SItemUniqueId>;

		witcher = (W3PlayerWitcher)owner;
		if(!witcher || !witcher.levelManager || skills.Size() != 167 || S_Perk_MAX != 102)
			return false;

		used = witcher.levelManager.GetPointsUsed(ESkillPoint);
		free = witcher.levelManager.GetPointsFree(ESkillPoint);
		// This narrow migration does not change researched mutations or inventory items.
		// A second restored manager may share an already-refunded levelManager.
		if(GetMutationsUsedSkillPoints() != 0 || !((used == 3 && free == 1) || (used == 0 && free == 4)))
			return false;
		if(mutagenSlots.Size() != 4)
			return false;
		for(i=0; i<mutagenSlots.Size(); i+=1)
		{
			if(mutagenSlots[i].equipmentSlot != EES_SkillMutagen1 + i || mutagenSlots[i].skillGroupID != i + 1)
				return false;
			keptMutagens.PushBack(mutagenSlots[i].item);
		}
		// The inspected save has nine empty synergy-bonus records.
		for(i=0; i<mutagenBonuses.Size(); i+=1)
			if(mutagenBonuses[i].count != 0 || IsNameValid(mutagenBonuses[i].abilityName))
				return false;

		// Read by array position/name, never by the incompatible remaster ESkill index.
		for(i=0; i<skills.Size(); i+=1)
		{
			if(skills[i].level <= 0 || skills[i].isCoreSkill)
				continue;
			if(skills[i].abilityName != 'sword_s22' && skills[i].abilityName != 'sword_s23' && skills[i].abilityName != 'sword_s24')
				return false;
			if(skills[i].level != 1 || skills[i].cost != 1 || skills[i].isTemporary)
				return false;
			if(removedNames.Contains(skills[i].abilityName))
				return false;
			removedNames.PushBack(skills[i].abilityName);
			learnedPoints += skills[i].level * skills[i].cost;
		}
		if(removedNames.Size() != 3 || learnedPoints != 3)
			return false;

		// Prepare the replacement before changing state; CacheSkills uses 4.04 XML.
		charStats.GetAbilitiesWithTag('SkillDefinitionName', skillDefs);
		if(skillDefs.Size() != 1)
			return false;
		CacheSkills(skillDefs[0], rebuiltSkills);
		if(rebuiltSkills.Size() != 102 || rebuiltSkills[S_Sword_1].skillType != S_Sword_1 || rebuiltSkills[S_Magic_s01].skillType != S_Magic_s01)
			return false;

		// Remove the stored ability names, including ones unknown to the 4.04 enum.
		for(i=0; i<skillAbilities.Size(); i+=1)
			if(IsNameValid(skillAbilities[i]))
				owner.RemoveAbilityAll(skillAbilities[i]);
		for(i=0; i<removedNames.Size(); i+=1)
			owner.RemoveAbilityAll(removedNames[i]);
		for(i=blockedAbilities.Size()-1; i>=0; i-=1)
			if(removedNames.Contains(blockedAbilities[i].abilityName))
				blockedAbilities.Erase(i);
		owner.RemoveAbilityAll('sword_adrenalinegain');
		owner.RemoveAbilityAll('magic_staminaregen');
		owner.RemoveAbilityAll('alchemy_potionduration');
		owner.RemoveAbilityAll('survival_vitality');
		skillAbilities.Clear();
		tempSkills.Clear();
		temporaryTutorialSkills.Clear();
		for(i=0; i<pathPointsSpent.Size(); i+=1)
			pathPointsSpent[i] = 0;

		skills = rebuiltSkills;
		totalSkillSlotsCount = 0;
		InitSkillSlots(false);
		mutagenSlots.Clear();
		LoadMutagenSlotsDataFromXML();
		// Restore the exact item IDs; only slot definitions revert to the 4.04 XML.
		for(i=0; i<mutagenSlots.Size(); i+=1)
			mutagenSlots[i].item = keptMutagens[i];
		mutagenBonuses.Clear();
		mutagenBonuses.Resize(GetSkillGroupsCount() + 1);
		InitSkills();
		PrecacheModifierSkills();

		// Preserve total points. perk_8 is a core skill and receives no refund.
		witcher.levelManager.NGE_SetFreePoints(free + used);
		witcher.levelManager.NGE_SetUsedPoints(0);
		SetToxicityOffset(0.f);
		LogChannel('CHR', "Remaster checkpoint migration: 167 -> 102 skills; 4 free, 0 used.");
		// The new 102-slot size makes subsequent Init calls a no-op.
		return true;
	}
