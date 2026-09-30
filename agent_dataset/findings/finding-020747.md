---
id: 20747
severity: "Medium"
---

# DoS in `MergingPool::claimRewards` function and potential DoS in `RankedBattle::claimNRN` function if called after a significant amount of rounds passed

## Description

```solidity
function claimRewards(
    string[] calldata modelURIs,
    string[] calldata modelTypes,
    uint256[2][] calldata customAttributes
)
    external
{
    uint256 winnersLength;
    uint32 claimIndex = 0;
    uint32 lowerBound = numRoundsClaimed[msg.sender];
    for (uint32 currentRound = lowerBound; currentRound < roundId; currentRound++) {
        numRoundsClaimed[msg.sender] += 1;
        winnersLength = winnerAddresses[currentRound].length;
        for (uint32 j = 0; j < winnersLength; j++) {
            if (msg.sender == winnerAddresses[currentRound][j]) {
                _fighterFarmInstance.mintFromMergingPool(
                    msg.sender,
                    modelURIs[claimIndex],
                    modelTypes[claimIndex],
                    customAttributes[claimIndex]
                );
                claimIndex += 1;
            }
        }
    }
    if (claimIndex > 0) {
        emit Claimed(msg.sender, claimIndex);
    }
}
```
Also there’s another nested loop which loops through all the winners each round. Thus, it will become very expensive to claim rewards and eventually leads to block gas limit. Due to which some users may never be able to claim their rewards.

Therefore, If user try to claim their rewards after many rounds has passed then due to the above mentioned loops, it will consume a lot of gas and eventually leads to block gas limit.

Similarly, the `RankedBattle::claimNRN` function loop through last claimed round ID to the latest round ID ( <https://github.com/code-423n4/2024-02-ai-arena/blob/main/src/RankedBattle.sol#L294> ):
```solidity
function claimNRN() external {
    require(numRoundsClaimed[msg.sender] < roundId, "Already claimed NRNs for this period");
    uint256 claimableNRN = 0;
    uint256 nrnDistribution;
    uint32 lowerBound = numRoundsClaimed[msg.sender];
    for (uint32 currentRound = lowerBound; currentRound < roundId; currentRound++) {
        nrnDistribution = getNrnDistribution(currentRound);
        claimableNRN += (
            accumulatedPointsPerAddress[msg.sender][currentRound] * nrnDistribution
        ) / totalAccumulatedPoints[currentRound];
        numRoundsClaimed[msg.sender] += 1;
    }
    if (claimableNRN > 0) {
        amountClaimed[msg.sender] += claimableNRN;
        _neuronInstance.mint(msg.sender, claimableNRN);
        emit Claimed(msg.sender, claimableNRN);
    }
}
```
Although, it’s relatively difficult to reach the block gas limit in `claimNRN` function as compared to `claimRewards` function, but still it’s possible.

## Proof of Concept

For `claimRewards` function, Add the below function in `MergingPool.t.sol`:
```solidity
function testClaimRewardsDOS() public {
    address user1 = vm.addr(1);
    address user2 = vm.addr(2);
    address user3 = vm.addr(3);

    _mintFromMergingPool(user1);
    _mintFromMergingPool(user2);
    _mintFromMergingPool(user3);

    uint offset = 35;
    uint totalWin = 9;

    uint256[] memory _winnersGeneral = new uint256[](2);
    _winnersGeneral[0] = 0;
    _winnersGeneral[1] = 1;

    uint256[] memory _winnersUser = new uint256[](2);
    _winnersUser[0] = 0;
    _winnersUser[1] = 2;
    for (uint i = 0; i < offset * totalWin; i++) {
        if (i % offset == 0) {
            _mergingPoolContract.pickWinner(_winnersUser);
        } else {
            _mergingPoolContract.pickWinner(_winnersGeneral);
        }
    }

    string[] memory _modelURIs = new string[](totalWin);
    string[] memory _modelTypes = new string[](totalWin);
    uint256[2][] memory _customAttributes = new uint256[2][](totalWin);
    for (uint i = 0; i < totalWin; i++) {
        _modelURIs[
            i
        ] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
        _modelTypes[i] = "original";
        _customAttributes[i][0] = uint256(1);
        _customAttributes[i][1] = uint256(80);
    }
    vm.prank(user3);
    uint gasBefore = gasleft();
    _mergingPoolContract.claimRewards(
        _modelURIs,
        _modelTypes,
        _customAttributes
    );
    uint gasAfter = gasleft();
    uint gasDiff = gasBefore - gasAfter;
    emit log_uint(gasDiff);
    uint256 numRewards = _mergingPoolContract.getUnclaimedRewards(user3);
    assertEq(numRewards, 0);
    assertGt(gasDiff, 4_000_000);
}
```
You can run the test by:
```
forge test --mt testClaimRewardsDOS -vv
```
Here I had considered 3 users, user1, user2, and user3. After each `offset` rounds, I picked `user3` as a winner. There were total of 315 ( `offset` * `totalWin` ) rounds passed and `user3` won in 9 of them. Then I tried to claim rewards for `user3` and it consumed more than 4M gas.

Also the more the round in which `user3` has won, the more gas it will consume. Even if `offset` is 1 and `totalWin` is 9 ( i.e total of 9 rounds out of which `user3` won in 9 of them ), it will consume more than 3.4M gas.

Also, we’ve considered only 2 winners per round, as the number of winners increases, the gas consumption will also increase due to the nested loop which loops through all the winners each round.

So if any user claim their rewards after many rounds has passed or if they have won in many rounds, it will consume a lot of gas and eventually leads to block gas limit.

For `claimNRN` function, Add the below function in `RankedBattle.t.sol`:
```solidity
function testClaimNRNDoS() public {
    _neuronContract.addSpender(address(_gameItemsContract));
    _gameItemsContract.instantiateNeuronContract(address(_neuronContract));
    _gameItemsContract.createGameItem(
        "Battery",
        "https://ipfs.io/ipfs/",
        true,
        true,
        10_000,
        1 * 10 ** 18,
        type(uint16).max
    );
    _gameItemsContract.setAllowedBurningAddresses(
        address(_voltageManagerContract)
    );

    address staker = vm.addr(3);
    _mintFromMergingPool(staker);
    vm.prank(_treasuryAddress);
    _neuronContract.transfer(staker, 400_000 * 10 ** 18);
    vm.prank(staker);
    _rankedBattleContract.stakeNRN(30_000 * 10 ** 18, 0);
    assertEq(_rankedBattleContract.amountStaked(0), 30_000 * 10 ** 18);

    address claimee = vm.addr(4);
    _mintFromMergingPool(claimee);
    vm.prank(_treasuryAddress);
    _neuronContract.transfer(claimee, 400_000 * 10 ** 18);
    vm.prank(claimee);
    _rankedBattleContract.stakeNRN(40_000 * 10 ** 18, 1);
    assertEq(_rankedBattleContract.amountStaked(1), 40_000 * 10 ** 18);

    uint offset = 35;
    uint totalWin = 9;
    for (uint i = 0; i < offset * totalWin; i++) {
        // 0 win
        // 1 tie
        // 2 loss
        if (i % offset == 0) {
            uint256 currentVoltage = _voltageManagerContract.ownerVoltage(
                claimee
            );
            if (currentVoltage < 100) {
                vm.prank(claimee);
                _gameItemsContract.mint(0, 1); //paying 1 $NRN for 1 batteries
                vm.prank(claimee);
                _voltageManagerContract.useVoltageBattery();
            }

            vm.prank(address(_GAME_SERVER_ADDRESS));
            _rankedBattleContract.updateBattleRecord(1, 50, 0, 1500, true);
        } else {
            uint256 currentVoltage = _voltageManagerContract.ownerVoltage(
                staker
            );
            if (currentVoltage < 100) {
                vm.prank(staker);
                _gameItemsContract.mint(0, 1); //paying 1 $NRN for 1 batteries
                vm.prank(staker);
                _voltageManagerContract.useVoltageBattery();
            }

            vm.prank(address(_GAME_SERVER_ADDRESS));
            _rankedBattleContract.updateBattleRecord(0, 50, 0, 1500, true);
        }
        _rankedBattleContract.setNewRound();
    }

    uint256 gasBefore = gasleft();
    vm.prank(claimee);
    _rankedBattleContract.claimNRN();
    uint256 gasAfter = gasleft();
    uint256 gasDiff = gasBefore - gasAfter;
    emit log_uint(gasDiff);
    assertGt(gasDiff, 1_000_000);
}
```
You can run the test by:
```
forge test --mt testClaimNRNDoS -vv
```
In the case of `claimNRN` function, it consumed more than 1M gas which is relatively less as compared to `claimRewards` function. But still it has potential to reach block gas limit.

Even for the users for whom these both functions doesn’t reach block gas limit, it can be very expensive and difficult for them to claim their rewards if some rounds has passed.

## Recommendation

It can be fixed by adding a parameter for the number of rounds to consider.

For `claimRewards` function, so the changes would look like:
```solidity
function claimRewards(
    string[] calldata modelURIs,
    string[] calldata modelTypes,
    uint256[2][] calldata customAttributes,
    uint32 totalRoundsToConsider
)
    external
{
    uint256 winnersLength;
    uint32 claimIndex = 0;
    uint32 lowerBound = numRoundsClaimed[msg.sender];
    require(lowerBound + totalRoundsToConsider < roundId, "MergingPool: totalRoundsToConsider exceeds the limit");
    for (uint32 currentRound = lowerBound; currentRound < lowerBound + totalRoundsToConsider; currentRound++) {
        numRoundsClaimed[msg.sender] += 1;
        winnersLength = winnerAddresses[currentRound].length;
        for (uint32 j = 0; j < winnersLength; j++) {
            if (msg.sender == winnerAddresses[currentRound][j]) {
                _fighterFarmInstance.mintFromMergingPool(
                    msg.sender,
                    modelURIs[claimIndex],
                    modelTypes[claimIndex],
                    customAttributes[claimIndex]
                );
                claimIndex += 1;
            }
        }
    }
    if (claimIndex > 0) {
        emit Claimed(msg.sender, claimIndex);
    }
}
```
For `claimNRN` function, so the changes would look like:
```solidity
function claimNRN(uint32 totalRoundsToConsider) external {
    require(numRoundsClaimed[msg.sender] < roundId, "Already claimed NRNs for this period");
    uint256 claimableNRN = 0;
    uint256 nrnDistribution;
    uint32 lowerBound = numRoundsClaimed[msg.sender];
    require(lowerBound + totalRoundsToConsider < roundId, "RankedBattle: totalRoundsToConsider exceeds the limit");
    for (uint32 currentRound = lowerBound; currentRound < lowerBound + totalRoundsToConsider; currentRound++) {
        nrnDistribution = getNrnDistribution(currentRound);
        claimableNRN += (
            accumulatedPointsPerAddress[msg.sender][currentRound] * nrnDistribution
        ) / totalAccumulatedPoints[currentRound];
        numRoundsClaimed[msg.sender] += 1;
    }
    if (claimableNRN > 0) {
        amountClaimed[msg.sender] += claimableNRN;
        _neuronInstance.mint(msg.sender, claimableNRN);
        emit Claimed(msg.sender, claimableNRN);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract provides two pull‑based reward functions – one for NFT rewards in the MergingPool and one for NRN token rewards in the RankedBattle – that iterate over every round that a user has not yet claimed. In claimRewards the code starts at the caller’s last claimed round (lowerBound) and loops forward to the current roundId, and for each round it iterates over the full list of winner addresses. Inside the inner loop it checks whether the caller is a winner and, if so, mints an NFT. Because both the number of rounds and the number of winners per round are unbounded, the total gas cost grows linearly with the product of those two dimensions. When a participant tries to claim after many rounds have elapsed, the nested loops can consume more gas than the block gas limit, causing the transaction to run out of gas and revert. The same pattern appears in claimNRN, where the function sums up claimable NRN across all unclaimed rounds; although the inner computation is cheaper, it still suffers from an unbounded iteration that can eventually hit the gas ceiling. The vulnerability was discovered during a formal audit when gas‑profiling tests showed that claimRewards required over four million gas after 315 rounds, and claimNRN exceeded one million gas after a similar number of rounds. The issue is hard to notice because the functions work correctly for a small number of rounds, and the failure only manifests after the protocol has been running for a long time or when a user has won many times. From a user’s perspective the expected outcome – receiving minted NFTs or NRN tokens – does not happen; instead the transaction fails, leaving the user’s balance unchanged and giving the impression that rewards are “missing” or that the contract is refusing to pay. All participants who have earned rewards in earlier rounds are affected, and the protocol’s overall trustworthiness is weakened because legitimate claimers can be denied service. The root cause is an unbounded loop over dynamic storage arrays without any pagination or limit, a classic gas‑exhaustion denial‑of‑service pattern. To remediate the problem the functions should be refactored to process a bounded number of rounds per call – for example by adding a parameter that caps the number of rounds considered, allowing callers to invoke the function repeatedly until all rewards are claimed – or by redesigning the reward distribution to use a pull‑based per‑round claim that does not require iterating over the entire history. This limits gas consumption, ensures that users can reliably receive their rewards, and eliminates the denial‑of‑service vector.
