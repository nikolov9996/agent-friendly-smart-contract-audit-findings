---
id: 15546
severity: "High"
---

# `GMXVault` can be blocked by a malicious actor

## Description

GMXVault can be blocked by malicious actor if he made a depositNative call with unpayable contract and the deposit then cancelled by the GMX exchange router (3rd party).
Users can deposit native tokens in vaults that either of its token pair is a WNT (wrapped native token) by calling GMXVault.depositNative payable function with the required deposit parameters (such as token, amount, minimum share amount, slippage & execution fees), then this function will invoke GMXDeposit.deposit with a msg.value equals the amount that the user wants to deposit + execution fees.
In GMXDeposit.deposit: various checks are made to ensure the sanity of the deposit parameters and the elligibility of the user to deposit, and to calculate the required tokenA & tokenB needed to deposit in the GMX protocol, then the sent native tokens are deposited in the WNT contract and an equivalent amount of WNT is transferred to the vault.
And before the call is made to the GMXManager.addLiquidity (where a call is going to be made to the GMX.exchangeRouter contract) to add liquidity; the status of the vault is checked if it's Open, if yes; then the status of the vault is set to Deposit so that no more deposits or withdrawls can be made (the vault will be blocked until the operation succeeds).
So if the operation succeeds in the GMX exchange router; the vault callback will invoke preocessDeposit function to finish the process and update the vault status to Open.
And if the operation of adding liquidity is cancelled by the GMX exchange router (3rd party); the vault callback will invoke processDepositCancellation function to rollback the process by repaying the lendingVaults debts and paying back the native tokens sent by the user, then update the vault status to Open so that the vault is open again for deposits and withdrawals.
Usually the deposit (liquidity addition to GMX protocol) fails if the user sets a very high slippage parameter when making a deposit (dp.slippage).

How can this be exploited to block the vault?
Imagine the following scenario:
If a malicious user deploys an unpayable contract (doesn't receive native tokens) and makes a call to the GMXVault.depositNative function with a very high slippage to ensure that the deposit will be cancelled by the GMX exchange router.
So when the deposit is cancelled and the vault callback processDepositCancellation function is invoked by the router; it will revert as it will try to send back the native tokens to the user who tried to make the deposit (which is the unpayable contract in our case).
And the status of the vault will be stuck in the Deposit state; so no more deposits or withdrawals can be made and the vault will be disabled.
The same scenario will happen if the user got blocklisted later by the deposited token contract (tokenA or tokenB), but the propability of this happening is very low as the GMX exchange router will add liquidity in two transactions with a small time separation between them!

The vault will be blocked as it will be stuck in the Deposit state; so no more deposits or withdrawals can be made.

## Proof of Concept

Code Instances:
GMXVault.depositNative

```solidity
  function depositNative(GMXTypes.DepositParams memory dp) external payable nonReentrant {
    GMXDeposit.deposit(_store, dp, true);
  }
```

GMXDeposit.deposit /L88

```solidity
_dc.user = payable(msg.sender);
```

GMXDeposit.processDepositCancellation /L209-210

```solidity
(bool success, ) = self.depositCache.user.call{value: address(this).balance}("");
      require(success, "Transfer failed.");
```

Foundry PoC:
A BlockerContract.sol is added to mimick the behaviour of an unpayable contract.
   add the following contract to the 2023-10-SteadeFi/test/gmx/local/BlockerContract.sol directory:

```solidity
   // SPDX-License-Identifier: MIT
   pragma solidity 0.8.21;

   import {GMXTypes} from "../../../contracts/strategy/gmx/GMXTypes.sol";
   import {GMXVault} from "../../../contracts/strategy/gmx/GMXVault.sol";

   contract BlockerContract {
       constructor() payable {}

       function callVault(
           address payable _vaultAddress,
           GMXTypes.DepositParams memory dp
       ) external {
           GMXVault targetVault = GMXVault(_vaultAddress);
           targetVault.depositNative{value: address(this).balance}(dp);
       }
   }
```
test_processDepositCancelWillBlockVault test is added to to the 2023-10-SteadeFi/test/gmx/local/GMXDepositTest.sol directory; where the blockerContract is deployed with some native tokens to cover deposit amount + execution fees, then this contract calls the depositNative via BlockerContract.callVault, where the exchange router tries to cancel the deposit but it will not be able as the BlockerContract can't receive back deposited native tokens, and the vault will be blocked.

   add this import statement and test to the GMXDepositTest.sol file :

```solidity
   import {BlockerContract} from "./BlockerContract.sol";
```

```solidity
     function test_processDepositCancelWillBlockVault() external {
           //1. deploy the blockerContract contract with a msg.value=deposit amount + execution fees:
           uint256 depositAmount = 1 ether;

           BlockerContract blockerContract = new BlockerContract{
               value: depositAmount + EXECUTION_FEE
           }();

           //check balance before deposit:
           uint256 blockerContractEthBalance = address(blockerContract).balance;
           assertEq(depositAmount + EXECUTION_FEE, blockerContractEthBalance);

           //2. preparing deposit params to call "depositNative" via the blockerContract:
           depositParams.token = address(WETH);
           depositParams.amt = depositAmount;
           depositParams.minSharesAmt = 0;
           depositParams.slippage = SLIPPAGE;
           depositParams.executionFee = EXECUTION_FEE;

           blockerContract.callVault(payable(address(vault)), depositParams);

           // vault status is "Deposit":
           assertEq(uint256(vault.store().status), 1);

           //3. the blockerContract tries to cancel the deposit, but it will not be able to do beacuse it's unpayable contract:
           vm.expectRevert();
           mockExchangeRouter.cancelDeposit(
               address(WETH),
               address(USDC),
               address(vault),
               address(callback)
           );

           // vault status will be stuck at "Deposit":
           assertEq(uint256(vault.store().status), 1);

           // check balance after cancelling the deposit, where it will be less than the original as no refund has been paid (the blockerContract is unpayable):
           assertLt(address(blockerContract).balance, blockerContractEthBalance);
       }
```
Test result:

```bash
   $ forge test --mt test_processDepositCancelWillBlockVault
   Running 1 test for test/gmx/local/GMXDepositTest.sol:GMXDepositTest
   [PASS] test_processDepositCancelWillBlockVault() (gas: 1419036)
   Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 24.62ms
   Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

## Recommendation

Add a mechanism to enable the user from redeeming his cancelled deposits (pulling) instead of sending it back to him (pushing).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is a denial‑of‑service condition that can permanently block a GMXVault when a deposit is cancelled and the contract attempts to push a refund to an address that cannot receive native ether. The vulnerability originates from the depositNative workflow: a user calls the payable function, the contract forwards the ether to the WNT wrapper and then marks the vault status as Deposit before invoking the external GMX exchange router to add liquidity. If the router rejects the operation – for example because the caller supplied an extreme slippage value – the router calls back into the vault’s processDepositCancellation routine. That routine tries to return the original ether to the depositor using a low‑level call (self.depositCache.user.call{value: address(this).balance}('')). When the depositor is a contract that deliberately rejects incoming ether (an unpayable contract), the call returns false, the require statement reverts, and the vault never reaches the code that would reset its status to Open. As a result the vault remains stuck in the Deposit state, preventing any further deposits or withdrawals. The impact is that the vault becomes unusable, locking user funds that are already inside the vault and halting any new liquidity provision for the protocol. The condition occurs only when a deposit is cancelled – typically due to a high slippage setting – and the refund recipient cannot accept ether. The affected parties are the vault’s users, the protocol that relies on the vault for liquidity, and any downstream contracts that expect the vault to be operational. The problem was uncovered during a security audit that included a crafted test contract (BlockerContract) that cannot receive ether; the test demonstrated that after a cancelled deposit the vault status stayed at Deposit and the contract’s balance decreased because the refund failed. The bug is subtle because the vault appears normal during successful deposits, and the status flag is only examined after a failure, making the lock‑up easy to miss in routine operation. To remediate the issue the refund logic should be changed from a push model to a pull model, allowing the depositor to withdraw the refunded ether at their own convenience, and the vault should ensure that its status is reset to Open even if the refund transfer fails, for example by using a safe‑transfer pattern or by catching the failure and proceeding with status restoration.
