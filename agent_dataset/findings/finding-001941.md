---
id: 1941
severity: "High"
---

# A single depositor can grief other

## Description

first epoch
After the CDO is initialized, deposits are allowed to provide the liquidity that will be used for the first epoch. During this same period, before the first epoch is started, withdrawals are also allowed (they are enabled when the contract is initialized), this makes sense, a depositor could request a withdrawal that would be withdrawable as soon as the first epoch is over, this depositor may have intentions to only seed liquidity for a single epoch, point is, depositors are allowed to request a withdrawal.
The problem that allows the exploit is that the requested withdrawals can actually be claimed right away, the IdleCreditVault.claimWithdrawRequest() relies on a condition that doesn't prevent withdrawal requests to be claimed before the first epoch ends.
```solidity
function claimWithdrawRequest(address _user) external returns (uint256 amount) {
    ...
    // lastWithdrawRequest was made on the current epoch. (`false && whatever` will always evaluate to false)
    claimed without needing to wait for finalization of the first epoch
    if (IIdleCDOEpochVariant(idleCDO).epochEndDate() != 0 && (epochNumber <= lastWithdrawRequest[_user])) {
        revert NotAllowed();
    }
    ...
}
```
This flaw allows for the attack described on the Attack Path section to be possible, causing to all the depositor's liquidity to be stolen.
As demonstrated on the coded PoC provided on the PoC section, a single depositor can continously deposit, request a withdraw and claim the requested withdraw before the first epoch starts.
• The requested withdraw claims the interests that would've been earnt during the first epoch, but, without needing to wait for the first epoch to end.
– That extra claimed amount comes from the deposits of the other depositors.
Since all deposits are sent directly to the CreditVault, all the extra liquidity taken by the griefer comes from the liquidity of the other depositors.
Initilization of the CDO contract sets the contract's state in such a way that it allows depositors to claim normal requested withdrawals without needing to wait until the first epoch is over.
Internal Pre-conditions
No epoch has started on the CDO. Liquidity (deposits) to start the first epoch is being collected before starting the first epoch.
External Pre-conditions
None.
Attack Path
1. Depositors provides liquidity on the CDO contract before the first epoch starts.
2. A depositor request a withdraw for all his deposits.
3. Depositor claims right away the requested withdraw.
4. The depositor receives his principal + the interest it would earn during the first epoch.
5. rinse && repeat step to continue draining the principal of the other depositors.
Deposits made before the first epoch can be stolen

## Proof of Concept

Add the next PoC on the IdleCreditVault.t.sol test file:
```solidity
function test_depositsBeforFirstEpochStartsCanBeStolenPoC() external {
    uint256 depositAmount = 10000 * ONE_SCALE;
    IdleCDOEpochVariant CDO = IdleCDOEpochVariant(address(idleCDO));
    assertEq(CDO.paused(),false,"Pause is True");
    assertEq(CDO.epochEndDate(),0,"epochEndDate != 0");
    IdleCreditVault strategy = IdleCreditVault(CDO.strategy());
    assert(strategy.getApr() != 0);
    address underlyingToken = CDO.token();
    address TranchTokenAA = CDO.AATranche();
    address user1 = makeAddr("user1");
    address user2 = makeAddr("user2");
    address user3 = makeAddr("user3");
    {
        deal(underlyingToken, user1, depositAmount);
        deal(underlyingToken, user2, depositAmount);
        deal(underlyingToken, user3, depositAmount);
        vm.startPrank(user1);
        IERC20(underlyingToken).approve(address(CDO), type(uint256).max);
        CDO.depositAA(depositAmount);
        vm.stopPrank();
        vm.startPrank(user2);
        IERC20(underlyingToken).approve(address(CDO), type(uint256).max);
        CDO.depositAA(depositAmount);
        vm.stopPrank();
        vm.startPrank(user3);
        IERC20(underlyingToken).approve(address(CDO), type(uint256).max);
        CDO.depositAA(depositAmount);
        vm.stopPrank();
    }
    uint256 initialStrategyUnderlingBalance = 3 * depositAmount;
    uint256 strategyUnderlyingBalance_before =
        IERC20(underlyingToken).balanceOf(address(strategy));
    assertEq(strategyUnderlyingBalance_before, initialStrategyUnderlingBalance);
    // on the CDO!
    uint256 user3UnderlyingBalance_before =
        IERC20(underlyingToken).balanceOf(address(user3));
    assertEq(user3UnderlyingBalance_before, 0);
    {
        vm.startPrank(user3);
        CDO.requestWithdraw(0,TranchTokenAA);
        CDO.claimWithdrawRequest();
        CDO.depositAA(IERC20(underlyingToken).balanceOf(address(user3)));
        CDO.requestWithdraw(0,TranchTokenAA);
        CDO.claimWithdrawRequest();
        CDO.depositAA(IERC20(underlyingToken).balanceOf(address(user3)));
        CDO.requestWithdraw(0,TranchTokenAA);
        CDO.claimWithdrawRequest();
        vm.stopPrank();
    }
    // claim the withdraw request, he claimed the interests as if the epoch would have ended!
    uint256 user3UnderlyingBalanc_after =
        IERC20(underlyingToken).balanceOf(address(user3));
    assertGt(user3UnderlyingBalanc_after, depositAmount);
    // User1 and User2
    uint256 strategyUnderlyingBalance_after =
        IERC20(underlyingToken).balanceOf(address(strategy));
    assertLt(strategyUnderlyingBalance_after, 2 * depositAmount);
}
```
Run the previous PoC with the next command: forge test --match-test test_depositsBeforFirstEpochStartsCanBeStolenPoC -vvvv

## Recommendation

The most straight forward mitigation is to initialize the epochEndDate to block.timestamp when the CDO is initialized.
• This will make that the validation on the IdleCreditVault.claimWithdrawRequest() to correctly prevent claiming withdrawal requests before the first epoch ends.
IdleCDOEpochVariant._additionalInit()
```solidity
function _additionalInit() internal virtual override {
    ...
    epochEndDate = block.timestamp;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logic error in the withdrawal flow of the Idle Credit Vault that allows a depositor to claim a withdrawal request immediately after it is made, even though the first epoch of the pool has not yet finished. The root cause is that the claimWithdrawRequest function checks the epoch end date and the epoch number against the lastWithdrawRequest mapping, but when the contract is first initialized the epochEndDate variable is zero. Because the condition "epochEndDate != 0 && (epochNumber <= lastWithdrawRequest[_user])" evaluates to false, the function does not block a claim made in the same epoch in which the request was created. An attacker can therefore deposit liquidity before the first epoch starts, request a full withdrawal, and call claimWithdrawRequest right away. The contract then pays out the principal plus the interest that would only have been earned after the epoch, and this extra amount is taken from the deposits of all other participants that are still waiting for the epoch to finish. The impact is that the pool’s total liquidity is drained, other users see their balances shrink or become zero, and the protocol loses trust because funds disappear without any explicit error. The exploit can be performed repeatedly: after each claim the attacker redeposits the received amount and repeats the request‑claim cycle, continuously siphoning liquidity from honest depositors. The vulnerability manifests only before any epoch has been started; once epochEndDate is set to a non‑zero timestamp the check works as intended. All depositors, the protocol’s liquidity providers, and any downstream users of the vault are affected. The issue was discovered during a manual audit when the tester wrote a proof‑of‑concept test that repeatedly deposited, requested, and claimed withdrawals before the first epoch, observing that the vault balance decreased while the attacker’s balance grew beyond the original deposit. The bug is subtle because the function appears to enforce a time lock, yet the uninitialized epochEndDate silently disables the protection, making it easy to miss in casual testing. To fix the problem the contract should initialise epochEndDate to the current block timestamp during deployment (or otherwise enforce that claimWithdrawRequest can only be called after the epoch end), ensuring that the early‑withdrawal guard is active from the start. This class of bug belongs to the broader category of “epoch timing bypass” or “premature claim” logic flaws where a state variable that controls access is left at its default value, allowing unauthorized actions that break the intended accounting guarantees of the system.
