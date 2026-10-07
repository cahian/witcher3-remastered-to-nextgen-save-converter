// Temporary helpers for the inspected checkpoint. No function runs automatically.
// Compiled and tested in Steam Next-Gen 4.04 on Steam Deck.

function ChrConversionStatus() : string
{
    var witcher : W3PlayerWitcher;
    var manager : W3PlayerAbilityManager;
    var skills : array<SSkill>;
    var items : array<SItemUniqueId>;
    var slots : array<SSkillSlot>;
    var mutagens : array<SMutagenSlot>;
    var i, learned, equipped : int;
    var message : string;

    witcher = GetWitcherPlayer();
    if(!witcher || !witcher.inv || !witcher.levelManager)
        return "CHR: player/inventory/level manager missing";
    manager = (W3PlayerAbilityManager)witcher.abilityManager;
    if(!manager)
        return "CHR: ability manager missing";
    skills = manager.GetPlayerSkills();
    slots = manager.GetSkillSlots();
    mutagens = manager.GetPlayerSkillMutagens();
    witcher.inv.GetAllItems(items);
    for(i=0; i<skills.Size(); i+=1)
        if(skills[i].level > 0 && !skills[i].isCoreSkill)
            learned += 1;
    for(i=0; i<items.Size(); i+=1)
        if(witcher.IsItemEquipped(items[i]))
            equipped += 1;
    message = "CHR level=" + witcher.GetLevel() + " skills=" + skills.Size()
        + " learned=" + learned + " free=" + witcher.levelManager.GetPointsFree(ESkillPoint)
        + " used=" + witcher.levelManager.GetPointsUsed(ESkillPoint)
        + " slots=" + slots.Size() + " mutagenSlots=" + mutagens.Size()
        + " items=" + items.Size() + " equipped=" + equipped
        + " combat=" + witcher.IsInCombat() + " saveLocked=" + theGame.AreSavesLocked();
    return message;
}

exec function chrstatus() : string
{
    var message : string;
    message = ChrConversionStatus();
    LogChannel('CHR', message);
    theGame.GetGuiManager().ShowNotification(message, 30.f, false);
    return message;
}

exec function chrpopup()
{
    var message : string;
    message = ChrConversionStatus();
    LogChannel('CHR', message);
    theGame.GetGuiManager().ShowUserDialogAdv(0, "Diagnostico da conversao", message, false, UDB_Ok);
}

// Each page shows 8 inventory stacks; equipped items include their exact equipment slot.
exec function chritems(optional page : int)
{
    var witcher : W3PlayerWitcher;
    var items : array<SItemUniqueId>;
    var i, start, end : int;
    var message, line : string;
    witcher = GetWitcherPlayer();
    if(!witcher || !witcher.inv)
        return;
    witcher.inv.GetAllItems(items);
    start = Max(0, page) * 8;
    end = Min(start + 8, items.Size());
    message = "Inventory stacks=" + items.Size() + ", page=" + page + "<br>";
    for(i=start; i<end; i+=1)
    {
        line = i + ": " + witcher.inv.GetItemName(items[i]) + " x" + witcher.inv.GetItemQuantity(items[i]);
        if(witcher.IsItemEquipped(items[i]))
            line += " [equipped " + witcher.GetItemSlot(items[i]) + "]";
        LogChannel('CHR', line);
        message += line + "<br>";
    }
    theGame.GetGuiManager().ShowUserDialogAdv(0, "Inventario da conversao", message, false, UDB_Ok);
}

// Explicit command only. expectedStacks must come from the independently inspected inventory.
// This invokes the normal native autosave request. The meaning of force is native code;
// actual file creation must be checked. It does not release locks or change combat/quest state.
exec function chrsave(expectedStacks : int, optional forceCheckpoint : bool)
{
    var witcher : W3PlayerWitcher;
    var manager : W3PlayerAbilityManager;
    var skills : array<SSkill>;
    var items : array<SItemUniqueId>;
    var i : int;
    witcher = GetWitcherPlayer();
    if(!witcher || !witcher.inv || !witcher.levelManager)
        return;
    manager = (W3PlayerAbilityManager)witcher.abilityManager;
    if(!manager)
        return;
    skills = manager.GetPlayerSkills();
    witcher.inv.GetAllItems(items);
    if(skills.Size() != 102 || witcher.levelManager.GetPointsFree(ESkillPoint) != 4
        || witcher.levelManager.GetPointsUsed(ESkillPoint) != 0
        || expectedStacks < 1 || items.Size() != expectedStacks)
    {
        theGame.GetGuiManager().ShowNotification("CHR save refused: validation mismatch", 30.f, false);
        return;
    }
    for(i=0; i<skills.Size(); i+=1)
        if(skills[i].level > 0 && !skills[i].isCoreSkill)
        {
            theGame.GetGuiManager().ShowNotification("CHR save refused: learned skill remains", 30.f, false);
            return;
        }
    if(forceCheckpoint)
    {
        LogChannel('CHR', "Explicit forced checkpoint after migration validation.");
        theGame.SaveGame(SGT_ForcedCheckPoint, -1);
    }
    else
    {
        LogChannel('CHR', "Explicit autosave request after checkpoint migration validation.");
        theGame.RequestAutoSave("checkpoint migration 4.04", true);
    }
}
