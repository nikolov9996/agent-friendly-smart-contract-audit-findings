---
id: 8617
severity: "High"
---

# Setting The Configuration with Arrays of Longer Than 1 Causes Incorrect Config

## Description

In the `WheelOfGuantune` contract the expectation is that the configuration will be set using the `configureWheel()` function. The input parameters expect an array of values as below:
```solidity
function configureWheel(
    uint256[] calldata segmentsPerReward,
    RewardType[] calldata rewardTypes,
    bytes[] calldata rewardValues,
    uint256 epochDuration
)
external
onlyOwner
```
When the array length of the input is longer than 1 then the loop that runs causes the storage variables to have a new item pushed to the storage variables to accommodate for the new configuration values as below:

```solidity
// iterate over the params to configure the wheel
for (uint256 i; i < expectedParamsLength; i++) {
    // first, get the values of the current iteration
    // note: the reward id is the configuration index + 1
    uint256 rewardId = i + 1;
    uint256 segments = segmentsPerReward[i];
    RewardType rewardType = rewardTypes[i];
    bytes memory rewardValue = rewardValues[i];
    // create new UintToUintMap instances for the new rewards config, resetting the previously configured values
    $.config.rewardTypeOfRewardId.push();
    $.config.rewardIdOfSegment.push();
    $.config.tokenIdOfRewardId.push();
    $.config.extraSpinsOfRewardId.push();
    $.config.gPointsOfRewardId.push();
    // code
}
```
The problem with this is that instead of each iteration being added to the new config record, each iteration creates it’s own new config record, ie:
Imagine 2 items in array
Iteration 1:
`$.config.rewardTypeOfRewardId[0].set` one entry with value of=====> a rewardId of the value 1.
Iteration 2:
`$.config.rewardTypeOfRewardId[1].set` one entry with value of=====> a rewardId of the value 2.
Instead of:
Iteration 1:
`$.config.rewardTypeOfRewardId[0].set` FIRST ENTRY=====> a rewardId of the value 1.
Iteration 2:
`$.config.rewardTypeOfRewardId[0].set` SECOND ENTRY=====> a rewardId of the value 2.

The getRewards() function is rendered non-functional, and the reward types are set incorrectly.

## Proof of Concept

```solidity
function test_OverwriteConfig() external {
    setBiggerConfig();
    WheelOfGuantune.Reward[] memory rewards = MockWheelOfGuantune(wheelproxy).getWheelRewards();
    for(uint256 i; i < rewards.length; i++){
        console.log("in loop");
        WheelOfGuantune.Reward memory tmpReward = rewards[i];
        console.log("[%d] rewardType is: %d", i, uint256(tmpReward.rewardType));
        console.log("[%d] value is: ", i);
        console.logBytes(tmpReward.value);
    }
    setBiggerConfig();
    WheelOfGuantune.Reward[] memory rewardsnew = MockWheelOfGuantune(wheelproxy).getWheelRewards();
    for(uint256 i; i < rewardsnew.length; i++){
        WheelOfGuantune.Reward memory tmpReward = rewardsnew[i];
        console.log("[%d] rewardType is: %d", i, uint256(tmpReward.rewardType));
        console.log("[%d] value is: ", i);
        console.logBytes(tmpReward.value);
    }
    setBiggerConfig();
    rewardsnew = MockWheelOfGuantune(wheelproxy).getWheelRewards();
    for(uint256 i; i < rewardsnew.length; i++){
        WheelOfGuantune.Reward memory tmpReward = rewardsnew[i];
        console.log("[%d] rewardType is: %d", i, uint256(tmpReward.rewardType));
        console.log("[%d] value is: ", i);
        console.logBytes(tmpReward.value);
    }
    console.log("Reward array length is: %d", rewardsnew.length);
}

function setBiggerConfig() public {
    uint256[] memory probabilityPerReward = new uint256[](2);
    uint256[] memory segmentsPerReward = new uint256[](2);
    WheelOfGuantune.RewardType[] memory rewardTypes = new WheelOfGuantune.RewardType[](2);
    bytes[] memory rewardValues = new bytes[](2);
    uint256 epochDuration = uint256(2 days);
    probabilityPerReward[0] = 15;
    segmentsPerReward[0] = 3;
    rewardTypes[0] = WheelOfGuantune.RewardType.GPoints;
    rewardValues[0] = abi.encode(8);
    probabilityPerReward[1] = 12;
    segmentsPerReward[1] = 2;
    rewardTypes[1] = WheelOfGuantune.RewardType.Nft;
    rewardValues[1] = abi.encode(5);
    vm.prank(veOwner);
    MockWheelOfGuantune(wheelproxy).configureWheel(segmentsPerReward, rewardTypes, rewardValues, epochDuration);
}
```

## Recommendation

Move the code that pushes new values outside the loop to only run once per call to configureWheel():
```solidity
function configureWheel(
    uint256[] calldata probabilityPerReward,
    uint256[] calldata segmentsPerReward,
    RewardType[] calldata rewardTypes,
    bytes[] calldata rewardValues,
    uint256 epochDuration
)
external
onlyOwner
{
    // code

    // prepare the new total segments value
    uint256 totalSegments;
    // create new UintToUintMap instances for the new rewards config, resetting the previously configured values
    $.config.rewardTypeOfRewardId.push();
    $.config.rewardIdOfSegment.push();
    $.config.tokenIdOfRewardId.push();
    $.config.extraSpinsOfRewardId.push();
    $.config.gPointsOfRewardId.push();
    // iterate over the params to configure the wheel
    for (uint256 i; i < expectedParamsLength; i++) {
        // first, get the values of the current iteration
        RewardType rewardType = rewardTypes[i];
        bytes memory rewardValue = rewardValues[i];
        // now, populate the new maps
        // cast to uint256 to store the enum value
        // code
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the wheel configuration routine of the WheelOfGuantune contract. The contract exposes a configureWheel() function that accepts parallel arrays describing each reward (segments per reward, reward type, reward value, and epoch duration). The implementation iterates over the length of the input arrays and, inside the loop, pushes new empty map structures (rewardTypeOfRewardId, rewardIdOfSegment, tokenIdOfRewardId, extraSpinsOfRewardId, gPointsOfRewardId) into the persistent configuration storage. Because the push operations are executed on every iteration, each loop creates a brand‑new configuration record instead of appending data to a single record. Consequently, the first iteration stores its reward at index 0 of the newly created map, the second iteration creates a second map and stores its reward at index 0 of that map, and so on. When the loop finishes, only the last iteration’s map contains a valid entry, while the earlier entries are lost or placed in separate, unreachable structures. The getRewards() view function, which reads from the configuration maps, therefore returns an incomplete or malformed reward list: the array length may be smaller than expected, reward types are shifted, and reward values can be missing. From a user’s perspective the UI may show no rewards, an empty reward list, or a reward of the wrong type, contradicting the expectation that a call to configureWheel with two rewards will produce two correctly indexed rewards. The bug is triggered whenever configureWheel is called with arrays longer than one element; a single‑element configuration works because only one push occurs. The issue was discovered during a manual audit and reproduced with a test that called configureWheel multiple times, observing that the reward array length remained constant and that reward data was overwritten. The problem is subtle because the code compiles without warnings and the push statements appear reasonable; however, the logical error of resetting the configuration on each iteration is not obvious without inspecting the loop body. The impact is high because the protocol’s core accounting – which determines which reward a user receives after a spin – becomes unreliable. Users may receive no reward, receive a reward of a different type, or experience a mismatch between the advertised odds and the actual distribution, potentially leading to loss of trust and financial loss if rewards are tied to token transfers. The vulnerability belongs to the class of “incorrect state initialization inside loops” or “configuration overwrite due to repeated storage allocation”. To remediate, the contract should allocate the configuration maps once before entering the loop, then populate the existing maps inside the loop without creating new instances on each iteration. This ensures that all reward entries are stored in the same persistent structure and that getRewards returns the full, correct set of rewards.
