---
id: 20739
severity: "High"
---

# Since you can reroll with a different fighterType than the NFT you own, you can reroll bypassing maxRerollsAllowed and reroll attributes based on a different fighterType

## Description

Can reroll attributes based on a different fighterType, and can bypass maxRerollsAllowed.

## Proof of Concept

`maxRerollsAllowed` can be set differently depending on the `fighterType`. Precisely, it increases as the generation of fighterType increases.
```solidity
    function incrementGeneration(uint8 fighterType) external returns (uint8) {
        require(msg.sender == _ownerAddress);
        generation[fighterType] += 1;
        maxRerollsAllowed[fighterType] += 1;
        return generation[fighterType];
    }
```
The `reRoll` function does not verify if the `fighterType` given as a parameter is actually the `fighterType` of the given tokenId. Therefore, it can use either 0 or 1 regardless of the actual type of the NFT.

This allows bypassing `maxRerollsAllowed` for additional reRoll, and to call `_createFighterBase` and `createPhysicalAttributes` based on a different `fighterType` than the actual NFT’s `fighterType`, resulting in attributes calculated based on different criteria.
```solidity
    function reRoll(uint8 tokenId, uint8 fighterType) public {
        require(msg.sender == ownerOf(tokenId));
        require(numRerolls[tokenId] < maxRerollsAllowed[fighterType]);
        require(_neuronInstance.balanceOf(msg.sender) >= rerollCost, "Not enough NRN for reroll");

        _neuronInstance.approveSpender(msg.sender, rerollCost);
        bool success = _neuronInstance.transferFrom(msg.sender, treasuryAddress, rerollCost);
        if (success) {
            numRerolls[tokenId] += 1;
            uint256 dna = uint256(keccak256(abi.encode(msg.sender, tokenId, numRerolls[tokenId])));
            (uint256 element, uint256 weight, uint256 newDna) = _createFighterBase(dna, fighterType);
            fighters[tokenId].element = element;
            fighters[tokenId].weight = weight;
            fighters[tokenId].physicalAttributes = _aiArenaHelperInstance.createPhysicalAttributes(
                newDna,
                generation[fighterType],
                fighters[tokenId].iconsType,
                fighters[tokenId].dendroidBool
            );
            _tokenURIs[tokenId] = "";
        }
    }
```
PoC:

  1. First, there is a bug that there is no way to set `numElements`, so add a numElements setter to FighterFarm. This bug has been submitted as a separate report.
```solidity
         function numElementsSetterForPoC(uint8 _generation, uint8 _newElementNum) public {
             require(msg.sender == _ownerAddress);
             require(_newElementNum > 0);
             numElements[_generation] = _newElementNum;
         }
```
  2. Add a test to the FighterFarm.t.sol file and run it. The generation of Dendroid has increased, and `maxRerollsAllowed` has increased. The user who owns the Champion NFT bypassed `maxRerollsAllowed` by putting the `fighterType` of Dendroid as a parameter in the `reRoll` function.
```solidity
         function testPoCRerollBypassMaxRerollsAllowed() public {
             _mintFromMergingPool(_ownerAddress);
             // get 4k neuron from treasury
             _fundUserWith4kNeuronByTreasury(_ownerAddress);
             // after successfully minting a fighter, update the model
             if (_fighterFarmContract.ownerOf(0) == _ownerAddress) {
                 uint8 maxRerolls = _fighterFarmContract.maxRerollsAllowed(0);
                 uint8 exceededLimit = maxRerolls + 1;
                 uint8 tokenId = 0;
                 uint8 fighterType = 0;
         
                 // The Dendroid's generation changed, and maxRerollsAllowed for Dendroid is increased
                 uint8 fighterType_Dendroid = 1;
         
                 _fighterFarmContract.incrementGeneration(fighterType_Dendroid);
         
                 assertEq(_fighterFarmContract.maxRerollsAllowed(fighterType_Dendroid), maxRerolls + 1);
                 assertEq(_fighterFarmContract.maxRerollsAllowed(fighterType), maxRerolls); // Champions maxRerollsAllowed is not changed
         
                 _neuronContract.addSpender(address(_fighterFarmContract));
         
                 _fighterFarmContract.numElementsSetterForPoC(1, 3); // this is added function for poc
         
                 for (uint8 i = 0; i < exceededLimit; i++) {
                     if (i == (maxRerolls)) {
                         // reRoll with different fighterType
                         assertEq(_fighterFarmContract.numRerolls(tokenId), maxRerolls);
                         _fighterFarmContract.reRoll(tokenId, fighterType_Dendroid);
                         assertEq(_fighterFarmContract.numRerolls(tokenId), exceededLimit);
                     } else {
                         _fighterFarmContract.reRoll(tokenId, fighterType);
                     }
                 }
             }
         }
```

## Recommendation

```solidity
    function reRoll(uint8 tokenId, uint8 fighterType) public {
        require(msg.sender == ownerOf(tokenId));
        require(numRerolls[tokenId] < maxRerollsAllowed[fighterType]);
        require(_neuronInstance.balanceOf(msg.sender) >= rerollCost, "Not enough NRN for reroll");
        require((fighterType == 1 && fighters[tokenId].dendroidBool) || (fighterType == 0 && !fighters[tokenId].dendroidBool), "Wrong fighterType");

        _neuronInstance.approveSpender(msg.sender, rerollCost);
        bool success = _neuronInstance.transferFrom(msg.sender, treasuryAddress, rerollCost);
        if (success) {
            numRerolls[tokenId] += 1;
            uint256 dna = uint256(keccak256(abi.encode(msg.sender, tokenId, numRerolls[tokenId])));
            (uint256 element, uint256 weight, uint256 newDna) = _createFighterBase(dna, fighterType);
            fighters[tokenId].element = element;
            fighters[tokenId].weight = weight;
            fighters[tokenId].physicalAttributes = _aiArenaHelperInstance.createPhysicalAttributes(
                newDna,
                generation[fighterType],
                fighters[tokenId].iconsType,
                fighters[tokenId].dendroidBool
            );
            _tokenURIs[tokenId] = "";
        }
    }
```
This report covers three consequences from the same root cause of fighter type validation: 1. more re-rolls, 2. rarer attribute switch, 3. generation attribute switch, with coded POC.

Note: [issue 212](https://github.com/code-423n4/2024-02-ai-arena-findings/issues/212)’s fix is a little more elegant.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the reRoll function of the fighter NFT contract. The function accepts a fighterType parameter supplied by the caller but does not verify that this parameter matches the actual type of the token identified by tokenId. Because the contract stores the allowed number of rerolls in a mapping keyed by fighterType, an attacker who owns a token of one type can pass the fighterType of another type that has a higher maxRerollsAllowed value. The require check therefore compares the token's current reroll count against a larger limit, allowing the attacker to exceed the intended maximum number of rerolls. After the payment is processed the contract calls internal routines that generate element, weight and physical attributes based on the supplied fighterType. Consequently the token can receive attributes that are calculated with the rules of a different class, such as a rarer element or a different generation weight. This flaw originates from missing validation of the relationship between tokenId and fighterType, an instance of improper input validation that breaks business logic. Exploitation is straightforward: the token owner calls reRoll repeatedly until the stored count reaches the original limit, then invokes reRoll once more with the alternate fighterType, causing numRerolls to increase beyond the intended cap and causing the token's attributes to be overwritten with values that would not be possible for its original class. The impact is that users can obtain more rerolls than the protocol permits and can artificially upgrade their NFTs, leading to an unfair advantage, potential devaluation of other tokens and disruption of the economic model that relies on rarity and generation constraints. The issue appears only when the contract owner has increased the maxRerollsAllowed for a particular fighterType, for example by incrementing the generation of that type. Any token holder of a different type can then exploit the mismatch. From a user perspective the symptom is that a token that should stop rerolling after a few attempts continues to accept reroll requests and suddenly shows an unexpected element or weight that does not match its class, contrary to the expectation that the NFT's attributes remain within its original tier. The bug was discovered during a manual audit that included a proof‑of‑concept test where the attacker called reRoll with a different fighterType and observed the counter exceed the limit and the attributes change. The problem is subtle because the function signature looks legitimate and the only visible check is the reroll count against a limit, which passes when the wrong type is supplied. To remediate the issue the contract should either remove the fighterType argument from reRoll and derive the type from the stored token data, or add an explicit require that the supplied fighterType matches the token's stored fighter type before checking the reroll limit and before invoking the attribute generation functions. This ensures that the business rules governing maxRerollsAllowed and attribute calculation are enforced consistently.
