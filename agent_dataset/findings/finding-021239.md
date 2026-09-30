---
id: 21239
severity: "High"
---

# Withdrawals of rebasing tokens can lead to insolvency and unfair distribution of protocol reserves

## Description

The [`WithdrawQueue`](https://github.com/code-423n4/2024-04-renzo/blob/main/contracts/Withdraw/WithdrawQueue.sol) contract allows users to withdraw their funds in various tokens, including liquid staking derivatives (LSDs) such as stETH. The [`withdraw()`](https://github.com/code-423n4/2024-04-renzo/blob/main/contracts/Withdraw/WithdrawQueue.sol#L206) function calculates the amount of the specified `_assetOut` token equivalent to the ezETH being withdrawn [using](https://github.com/code-423n4/2024-04-renzo/blob/main/contracts/Withdraw/WithdrawQueue.sol#L229) the `renzoOracle.lookupTokenAmountFromValue()` function. This amount is then stored in the `amountToRedeem` field of a new `WithdrawRequest` struct, which is added to the user’s `withdrawRequests` array and the token’s `claimReserve`.

When the user later calls [`claim()`](https://github.com/code-423n4/2024-04-renzo/blob/main/contracts/Withdraw/WithdrawQueue.sol#L279), the contract transfers the `amountToRedeem` to the user via the [`IERC20.transfer()`](https://github.com/code-423n4/2024-04-renzo/blob/main/contracts/Withdraw/WithdrawQueue.sol#L305) function.

However, this implementation does not properly handle rebasing tokens like stETH. The stETH balance of the `WithdrawQueue` can change between the time a withdrawal is recorded and when it is claimed, even though the contract’s stETH shares remain constant.

If the stETH balance decreases during this period due to a rebasing event (e.g., a slashing of the staked ETH), the `amountToRedeem` stored in the `WithdrawRequest` may exceed the contract’s actual stETH balance at the time of claiming. As a result, the withdrawal can fail or result in the user receiving a larger share of the total protocol reserves than intended.

The issue can be illustrated by comparing the behavior of withdrawals for non-rebasing and rebasing LSDs:

1. Non-rebasing LSD (e.g., wBETH):

   * User A requests a withdrawal of 10 wBETH (worth 10 ETH) from the protocol.
   * While the withdrawal is pending, wBETH’s underlying staked ETH suffers a 50% slashing event.
   * The price of wBETH drops to 0.5 ETH per token due to the slashing.
   * When User A claims their withdrawal, they receive 10 wBETH, which is now worth only 5 ETH.
   * User A bears the loss from the slashing event.
2. Rebasing LSD (e.g., stETH):

   * User B requests a withdrawal of 10 stETH (worth 10 ETH) from the protocol.
   * While the withdrawal is pending, the underlying staked ETH suffers a 50% slashing event.
   * Everyone’s stETH balances are rebased to maintain the ETH peg, so the protocol’s stETH balance is halved.
   * When User B claims their withdrawal, they receive the original 10 stETH (still worth 10 ETH) as recorded in the withdrawal request.
   * The protocol bears the loss from the slashing event, as it has sent out more than its fair share of the rebased stETH balance.

## Proof of Concept

We can validate the vulnerability through a Foundry test case POC. This test case will simulate the exploit scenario and confirm the issue by performing the following actions:

1. Alice and Bob initiate withdrawals of their ezETH shares for stETH.
2. Simulate a negative rebasing event by transferring 10% of stETH balance from the `withdrawQueue` contract.
3. Alice claims her withdrawal successfully, receiving her original stETH amount.
4. Bob’s attempt to claim his withdrawal fails due to insufficient stETH balance.
5. Verify that ezETH supply remains unchanged while TVL is significantly reduced, demonstrating ezETH becoming uncollateralized.

The PoC can be run in Foundry by using the setup and mock infra provided [here](https://gist.github.com/3docSec/a4bc6254f709a6218907a3de370ae84e).

```solidity
pragma solidity ^0.8.19;

import "contracts/Errors/Errors.sol";
import "./Setup.sol";

contract H6 is Setup {

    function testH6() public {
        // we set the buffer to something reasonably high
        WithdrawQueueStorageV1.TokenWithdrawBuffer[] memory buffers = new WithdrawQueueStorageV1.TokenWithdrawBuffer[](2);

        buffers[0] = WithdrawQueueStorageV1.TokenWithdrawBuffer(address(stETH), 100e18 - 1);
        buffers[1] = WithdrawQueueStorageV1.TokenWithdrawBuffer(address(cbETH), 100e18 - 1);

        vm.startPrank(OWNER);
        withdrawQueue.updateWithdrawBufferTarget(buffers);

        // we'll be using stETH and cbETH with unitary price for simplicity
        stEthPriceOracle.setAnswer(1e18);
        cbEthPriceOracle.setAnswer(1e18);

        // and we start with 0 TVL
        (, , uint tvl) = restakeManager.calculateTVLs();
        assertEq(0, tvl);

        // let's then imagine that Alice and Bob hold 90 and 10 ezETH each
        address alice = address(1234567890);
        address bob = address(1234567891);
        stETH.mint(alice, 100e18);
        vm.startPrank(alice);
        stETH.approve(address(restakeManager), 100e18);
        restakeManager.deposit(IERC20(address(stETH)), 100e18);
        ezETH.transfer(bob, 10e18);

        // ✅ TVL and balance are as expected
        (, , tvl) = restakeManager.calculateTVLs();
        assertEq(100e18, tvl);
        assertEq(90e18, ezETH.balanceOf(alice));
        assertEq(10e18, ezETH.balanceOf(bob));

        // Now Bob initiates withdrawal of their shares
        vm.startPrank(bob);
        ezETH.approve(address(withdrawQueue), 10e18);
        withdrawQueue.withdraw(10e18, address(stETH));

        // Alice, too, initiates withdrawal of their shares
        vm.startPrank(alice);
        ezETH.approve(address(withdrawQueue), 90e18 - 1);
        withdrawQueue.withdraw(90e18 - 1, address(stETH));

        // ☢️ time passes, and an stETH negative rebasing happens, wiping
        // 10% of the balance
        vm.startPrank(address(withdrawQueue));
        stETH.transfer(address(1), 10e18);

        vm.warp(block.timestamp + 10 days);

        // 🚨 now, since WithdrawQueue checked availability at withdrawal initiation
        // only and didn not account for the possibility of rebases, the 10% loss
        // has been completely dodged by Alice and is attributed to the last
        // user exiting.
        vm.startPrank(alice);
        withdrawQueue.claim(0);
        assertEq(90e18 - 1, stETH.balanceOf(alice));

        // 🚨 not only Bob can't withdraw
        vm.startPrank(bob);
        vm.expectRevert();
        withdrawQueue.claim(0);

        // 🚨 but ezETH as a whole also became completely uncollateralized
        assertEq(10e18 + 1, ezETH.totalSupply());
        (, , tvl) = restakeManager.calculateTVLs();
        assertEq(1, tvl);
    }
}
```

## Recommendation

To address the issue of unfair distribution of funds when withdrawing rebasing tokens like stETH, the `WithdrawQueue` contract should store and transfer the user’s withdrawal as stETH shares instead of a fixed stETH amount.

When a user initiates a withdrawal with stETH as the `_assetOut`, the contract should convert the calculated `amountToRedeem` to stETH shares using the `stETH.getSharesByPooledEth()` function:

```solidity
uint256 sharesAmount = IStETH(stETHAddress).getSharesByPooledEth(amountToRedeem);
```

The resulting `sharesAmount` should be stored in the `WithdrawRequest` struct instead of the `amountToRedeem`.

When the user calls `claim()`, the contract should transfer the stETH shares directly to the user using the `stETH.transferShares()` function:

```solidity
IStETH(stETHAddress).transferShares(msg.sender, sharesAmount);
```

By storing and transferring stETH shares instead of a fixed stETH amount, the contract ensures that each user receives their fair share of the stETH balance, regardless of any rebasing events that occur between the time of the withdrawal request and the claim.

To implement this mitigation, the contract should:

1. Check if the `_assetOut` is stETH when processing a withdrawal request.
2. If so, convert the `amountToRedeem` to stETH shares using `stETH.getSharesByPooledEth()` and store the shares amount in the `WithdrawRequest` struct.
3. Update the `claim()` function to check if the withdrawal is in stETH and, if so, transfer the shares directly using `stETH.transferShares()` instead of using the standard `IERC20.transfer()` function.

Note that this mitigation is specific to stETH and may need to be adapted for other rebasing tokens that use a similar shares-based system.

Furthermore, the `claimReserve` and `withdrawalBufferTarget` for stETH would also need to be stored in shares and converted to underlying in TVL and withdraw buffer calculations, respectively.

I’m going to sustain the high severity on the grounds that:

* If the stEth balance increases, as it normally does, users lose value in comparison to non-rebasing LSTs.
* If the stEth balance decreases, the protocol loses value in comparison to non-rebasing LSTs.
* If the stEth balance decreases, the protocol might DoS.

The users that win in a slashing event are not the same users that lose during normal operation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the WithdrawQueue contract that manages user withdrawals of various assets, including liquid staking derivatives (LSDs) that implement a rebasing mechanism such as stETH. When a user calls withdraw(), the contract queries an oracle to compute a fixed token amount (amountToRedeem) that represents the value of the user’s ezETH share in the chosen output asset. This amount is stored directly in a WithdrawRequest struct and later transferred to the user in claim() via a standard ERC‑20 transfer. The root cause is that the contract treats rebasing tokens as if their balances were static, ignoring that the underlying token balance can change between the time the withdrawal request is recorded and the moment it is claimed. Rebasing tokens keep a constant number of shares while the underlying pooled ETH value per share can increase or decrease after events such as slashing or reward distribution. Because the WithdrawQueue records a fixed token amount rather than the corresponding share count, a negative rebasing event (for example a 10 % slashing of the stETH pool) reduces the contract’s actual stETH balance while the stored amountToRedeem remains unchanged. When the first claimant executes claim(), the contract transfers the originally recorded amount, which now represents a larger proportion of the remaining pool than intended. Consequently the protocol disburses more value than it holds, causing later claimants to either receive less than expected or encounter a transfer failure. From the user’s perspective the symptoms are a missing or zero balance after a claim, or an unexpected revert when trying to withdraw, while the protocol’s reserves become under‑collateralised and may even become insolvent. The issue manifests only for assets that rebase; non‑rebasing tokens such as wBETH behave correctly because their token balance tracks value one‑to‑one. The problem was uncovered during a formal audit by simulating a negative rebasing event in a Foundry test, which showed that early withdrawers could extract the full pre‑rebasing amount while later withdrawers were left with insufficient funds. The bug is subtle because the contract’s balance checks occur at request time, giving a false sense of safety, and the rebasing adjustment is not visible on‑chain until after the event. The recommended mitigation is to store and transfer the user’s entitlement in terms of shares rather than a fixed token amount. By converting the oracle‑derived value to stETH shares with getSharesByPooledEth() at withdrawal time and later transferring those shares with transferShares(), the protocol ensures each user receives a proportional slice of the current pool regardless of rebasing. Similar share‑based accounting should be applied to claimReserve and buffer calculations. This change restores accounting integrity, prevents unfair profit extraction, and protects the protocol from insolvency caused by rebasing token dynamics.
