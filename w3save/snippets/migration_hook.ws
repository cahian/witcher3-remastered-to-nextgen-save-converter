
        if(isFromLoad && skills.Size() == 167)
        {
            if(!MigrateInspectedRemasterCheckpoint())
            {
                LogAssert(false, "Remaster checkpoint migration preconditions failed");
                return false;
            }
        }
