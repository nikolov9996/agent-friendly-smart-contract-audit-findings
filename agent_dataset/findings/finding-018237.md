---
id: 18237
severity: "High"
---

# Users will be able to purchase fewer NFTs than the project had anticipated

## Description

Users will be able to purchase fewer NFTs than the project had anticipated. The project had expected that users would be able to purchase a range of variations using both text and emoji characters. However, in reality, users will only be able to purchase a range of variations using emoji characters.

For example, the list of characters available for users to choose from is as follows ![image](https://i.ibb.co/NjnD4Tf/Screenshot-from-2023-03-20-00-22-23.png)

For instance, if a user chooses to mint an NFT namespace using font class 2 and the single letter 𝒶, then theoretically all other users should be able to mint font class 0 using the first emoji in the list, font class 1 using the single letter “a,” font class 3 using the single letter 𝓪, and so on, the first letter on every class will be. However, in reality, they will not be able to do so.

I consider this to be a critical issue because the project may not be able to sell as many NFTs as expected, potentially resulting in a loss of funds.

Here is how nft name and their svg will look like from what I described above. As you can see emoji replaced letters in the name.

![image](https://i.ibb.co/L8NDWgy/Screenshot-from-2023-03-20-17-35-49.png)

This is a function that creates namespace out of tray.
    
    canto-namespace-protocol/src/Namespace.sol#L110
```solidity
        function fuse(CharacterData[] calldata _characterList) external {
            uint256 numCharacters = _characterList.length;
            if (numCharacters > 13 || numCharacters == 0) revert InvalidNumberOfCharacters(numCharacters);
            uint256 fusingCosts = 2**(13 - numCharacters) * 1e18;
            SafeTransferLib.safeTransferFrom(note, msg.sender, revenueAddress, fusingCosts);
            uint256 namespaceIDToMint = ++nextNamespaceIDToMint;
            Tray.TileData[] storage nftToMintCharacters = nftCharacters[namespaceIDToMint];
            bytes memory bName = new bytes(numCharacters * 33); // Used to convert into a string. Can be 33 times longer than the string at most (longest zalgo characters is 33 bytes)
            uint256 numBytes;
            // Extract unique trays for burning them later on
            uint256 numUniqueTrays;
            uint256[] memory uniqueTrays = new uint256[](_characterList.length);
            for (uint256 i; i < numCharacters; ++i) {
                bool isLastTrayEntry = true;
                uint256 trayID = _characterList[i].trayID;
                uint8 tileOffset = _characterList[i].tileOffset;
                // Check for duplicate characters in the provided list. 1/2 * n^2 loop iterations, but n is bounded to 13 and we do not perform any storage operations
                for (uint256 j = i + 1; j < numCharacters; ++j) {
                    if (_characterList[j].trayID == trayID) {
                        isLastTrayEntry = false;
                        if (_characterList[j].tileOffset == tileOffset) revert FusingDuplicateCharactersNotAllowed();
                    }
                }
                Tray.TileData memory tileData = tray.getTile(trayID, tileOffset); // Will revert if tileOffset is too high
                uint8 characterModifier = tileData.characterModifier;
    
                if (tileData.fontClass != 0 && _characterList[i].skinToneModifier != 0) {
                    revert CannotFuseCharacterWithSkinTone();
                }
                
                if (tileData.fontClass == 0) {
                    // Emoji
                    characterModifier = _characterList[i].skinToneModifier;
                }
                bytes memory charAsBytes = Utils.characterToUnicodeBytes(0, tileData.characterIndex, characterModifier);
    ... 
```

[canto-namespace-protocol/src/Namespace.sol#L110](https://github.com/code-423n4/2023-03-canto-identity/blob/077372297fc419ea7688ab62cc3fd4e8f4e24e66/canto-namespace-protocol/src/Namespace.sol#L110)

There is a bug in this line of code where a character is retrieved from tile data. Instead of passing `tileData.fontClass`, we are passing `0`.
    
```solidity
                bytes memory charAsBytes = Utils.characterToUnicodeBytes(0, tileData.characterIndex, characterModifier);
```

Due to this bug, the names for all four different font classes will be the same. As a result, they will point to an existing namespace, and later, there will be a check for the existence of that name (token) using NameAlreadyRegistered.
    
```solidity
            string memory nameToRegister = string(bName);
            uint256 currentRegisteredID = nameToToken[nameToRegister];
            if (currentRegisteredID != 0) revert NameAlreadyRegistered(currentRegisteredID);
```

## Proof of Concept

Here is the test that you can run
    
```solidity
        function testFailMintSameCharacterIndex() public {
            address user = user1;
            note.mint(user, 10000e18);
            endPrelaunchAndBuyOne(user);
    
            uint256[] memory trayIds = buyTray(user, 3);
            vm.startPrank(user);
            note.approve(address(ns), type(uint256).max);
            Namespace.CharacterData[] memory list = new Namespace.CharacterData[](
                1
            );
    //      fuse tile with fontClass=8,characterIndex=1
            list[0] = Namespace.CharacterData(trayIds[1], 4, 0);
            Tray.TileData memory tileData = tray.getTile(trayIds[1], 4);
            console.log(tileData.characterIndex);//1
            console.log(tileData.fontClass);//8
            ns.fuse(list);
    
    //      fuse tile with fontClass=4,characterIndex=1
            list[0] = Namespace.CharacterData(trayIds[2], 3, 0);
            tileData = tray.getTile(trayIds[2], 3);
            console.log(tileData.characterIndex);//1
            console.log(tileData.fontClass);//4
            vm.expectRevert(
                abi.encodeWithSelector(Namespace.NameAlreadyRegistered.selector, 1)
            );
            ns.fuse(list);
        }
```

## Recommendation

Pass font class instead of 0
    
```solidity
    -            bytes memory charAsBytes = Utils.characterToUnicodeBytes(0, tileData.characterIndex, characterModifier);
    +            bytes memory charAsBytes = Utils.characterToUnicodeBytes(tileData.fontClass, tileData.characterIndex, characterModifier);
```

Agree, leftover from earlier, will be changed.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logic error in the namespace creation function where the font class of a character is ignored. When the contract builds the Unicode representation of a character it calls Utils.characterToUnicodeBytes with a hard‑coded first argument of 0, which forces every character to be treated as an emoji class regardless of the actual fontClass stored in the tile data. Because the name of a namespace is derived from this Unicode string, all characters that share the same characterIndex produce identical names even when they belong to different font classes. The contract then checks the name against a registry and reverts with NameAlreadyRegistered if the name already exists. Consequently, a user who tries to mint a distinct NFT using a different font class (for example a styled letter instead of an emoji) will be blocked because the name collides with a previously minted token. This reduces the set of purchasable variations to only emoji characters, preventing the project from selling the full range of NFTs it advertised. The issue manifests whenever the fuse function is invoked with a character whose fontClass is non‑zero; the UI may show the expected selection but the transaction fails or mints an NFT with an unexpected visual (emoji instead of the chosen style). It was discovered during a security audit by reproducing a test that mints the same characterIndex with two different font classes and observing the NameAlreadyRegistered revert. The bug is subtle because the visual output looks similar and the error only appears at the name‑collision check, making it easy to miss during manual testing. The proper fix is to pass tileData.fontClass to Utils.characterToUnicodeBytes instead of the constant 0, ensuring each font class generates a unique Unicode string and thus a unique namespace name.
