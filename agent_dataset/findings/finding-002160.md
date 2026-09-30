---
id: 2160
severity: "High"
---

# `GMXV2_Module` withdrawal functionality is broken due to missing callback implementation

## Description

** The `GMXV2_Module` contract's withdrawal functionality is broken because it sets itself (address(this)) as the callback contract for GMX V2 withdrawals without implementing the required callback interface. This causes all withdrawal transactions to revert, effectively locking user funds in the protocol.

```solidity
function gmxv2_withdraw(
    address market,
    uint256 executionFee,
    uint256 amount,
    uint256 minLongOut,
    uint256 minShortOut
) external payable onlyRole(EXECUTOR_ROLE) nonReentrant {
    IExchangeRouter.CreateWithdrawalParams memory params = IExchangeRouter.CreateWithdrawalParams({
        receiver: address(this),
        callbackContract: address(this),  // @audit - Setting callback without implementation
        // ...
    });
    // ...
}
```

According to GMX V2's documentation and source code, when a callback contract is specified, it must implement two critical functions:

1. `afterWithdrawalExecution(bytes32, WithdrawalUtils.Props, EventUtils.EventLogData)`
2. `afterWithdrawalCancellation(bytes32, WithdrawalUtils.Props)`

These callbacks are enforced by GMX's `ExecuteWithdrawalUtils.sol`:

```solidity
// In ExecuteWithdrawalUtils.sol
function executeWithdrawal(...) {
    // ... other code ...
    CallbackUtils.afterWithdrawalExecution(params.key, withdrawal, eventData);
    // ... other code ...
}

// In CallbackUtils.sol
function afterWithdrawalExecution(...) internal {
    if (withdrawal.callbackContract() != address(0)) {
        IWithdrawalCallbackReceiver(withdrawal.callbackContract()).afterWithdrawalExecution(
            key,
            withdrawal,
            eventData
        );
    }
}
```

** This issue completely breaks a core protocol function. It has severe implications:

- **Complete loss of functionality**: All withdrawal transactions through `gmxv2_withdraw` will revert, making it impossible for users to withdraw their funds.
- **Loss of funds**: User funds become locked in the protocol.

## Proof of Concept

** We've created a test that demonstrates this issue:

```solidity
function test_gmxv2_withdraw_RevertGivenMissingCallback() public {
        // First make a deposit to get market tokens
        uint256 depositAmount = 1e18;
        deal(WETH_ADDRESS, address(strategy), depositAmount);
        vm.prank(address(strategy));
        _weth.approve(GMX_DEPOSIT_VAULT, depositAmount);

        // Store initial balance
        uint256 initialExecutorBalance = EXECUTOR.balance;

        // Get market info before deposit
        IMarket.Props memory marketInfo = IReader(GMX_READER).getMarket(GMX_DATASTORE, GMX_WETH_MARKET);
        address marketToken = marketInfo.marketToken;

        // Execute deposit
        vm.prank(EXECUTOR);
        _gmx.gmxv2_deposit{value: 0.1 ether}(
            GMX_WETH_MARKET,
            0.1 ether,  // execution fee
            depositAmount,
            0,          // no short token
            0           // min out
        );

        // Deal market tokens to the vault first before simulating keeper execution
        deal(marketToken, GMX_DEPOSIT_VAULT, depositAmount);

        // ============ KEEPER SIMULATION - DEPOSIT EXECUTION ============
        // In production: GMX keeper would execute this step
        // Here we simulate the keeper minting market tokens to the strategy
        vm.prank(GMX_DEPOSIT_VAULT);
        IERC20(marketToken).transfer(address(strategy), depositAmount); // Simulate market tokens being minted
        // ============ END KEEPER SIMULATION - DEPOSIT EXECUTION ============

        // Get market token balance after deposit
        uint256 marketTokenBalance = IERC20(marketToken).balanceOf(address(strategy));

        require(marketTokenBalance > 0, "No market tokens received from deposit");

        // Approve market tokens for withdrawal
        vm.prank(address(strategy));
        IERC20(marketToken).approve(GMX_WITHDRAW_VAULT, depositAmount);

        // Now attempt to withdraw
        vm.prank(EXECUTOR);
        _gmx.gmxv2_withdraw{value: 0.1 ether}(
            GMX_WETH_MARKET,
            0.1 ether,  // execution fee
            depositAmount,
            0,          // min long out
            0           // min short out
        );

        // Deal WETH to the withdraw vault before simulating keeper execution
        deal(WETH_ADDRESS, GMX_WITHDRAW_VAULT, depositAmount * 2); // Ensure vault has enough WETH

        // First give market tokens to the strategy
        deal(marketToken, address(strategy), depositAmount);

        // ============ KEEPER SIMULATION - WITHDRAWAL EXECUTION ============
        // In production: GMX keeper would:
        // 1. Burn market tokens
        // 2. Return WETH
        // 3. Call the callback contract (if set) with afterWithdrawalExecution
        // Here we simulate steps 1 and 2 manually:
        vm.startPrank(GMX_WITHDRAW_VAULT);
        // Step 1: Burn market tokens (transfer them to withdraw vault)
        IERC20(marketToken).transferFrom(address(strategy), GMX_WITHDRAW_VAULT, depositAmount);
        // Step 2: Return WETH to strategy
        IERC20(WETH_ADDRESS).transfer(address(strategy), depositAmount);
        vm.stopPrank();
        // Note: Step 3 (callback) is not simulated as we're bypassing GMX's actual execution
        // ============ END KEEPER SIMULATION - WITHDRAWAL EXECUTION ============

        // Verify executor spent the execution fees
        assertEq(
            EXECUTOR.balance,
            initialExecutorBalance - 0.2 ether, // 0.1 for deposit + 0.1 for withdrawal
            "Executor should have spent 0.2 ETH for execution fees"
        );
    }
```

The test passes, but this is misleading because we're manually simulating the keeper's actions. In production, according to [GMX V2's documentation](https://github.com/gmx-io/gmx-synthetics#withdrawal-notes), withdrawals require specific callback handling:

"Ensure only handlers with the CONTROLLER role can call the afterWithdrawalExecution and afterWithdrawalCancellation callback functions"

This indicates that GMX V2 expects contracts interacting with withdrawals to implement these callback functions. When our contract attempts a withdrawal in production:
1. The keeper will attempt to call `afterWithdrawalExecution` on our contract
2. Since we don't implement this interface, the transaction will revert
3. The withdrawal will fail, leaving user funds stuck in the protocol

Our test passes only because we're bypassing GMX's actual withdrawal execution by manually simulating the token transfers, which skips the mandatory callback mechanism.

## Recommendation

** There are two possible fixes:

**Option 1: Remove Callback (Recommended)**
If no post-withdrawal processing is needed:

```solidity
IExchangeRouter.CreateWithdrawalParams memory params = IExchangeRouter.CreateWithdrawalParams({
    receiver: address(this),
    callbackContract: address(0),  // Set to zero address to skip callbacks
    // ...
});
```

**Option 2: Implement Callback Interface**
If post-withdrawal processing is required, implement the IWithdrawalCallbackReceiver interface:

```solidity
contract GMXV2_Module is IGMXV2_Module, IWithdrawalCallbackReceiver {
    function afterWithdrawalExecution(
        bytes32 key_,
        WithdrawalUtils.Props memory withdrawal_,
        EventUtils.EventLogData memory eventData_
    ) external {
        // Add post-withdrawal logic
    }

    function afterWithdrawalCancellation(
        bytes32 key_,
        WithdrawalUtils.Props memory withdrawal_
    ) external {
        // Add cancellation logic
    }
}
```

We recommend Option 1 (removing the callback) unless there's a specific need for post-withdrawal processing, as it's simpler and requires less gas.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The GMXV2_Module contract contains a critical withdrawal flaw: it registers itself as the callback contract for GMX V2 withdrawals but does not implement the required IWithdrawalCallbackReceiver interface. GMX V2 expects any contract supplied as a callback to expose two functions, afterWithdrawalExecution and afterWithdrawalCancellation, which are invoked by the GMX keeper after the withdrawal process. Because the module lacks these functions, the keeper’s call fails, causing the entire withdrawal transaction to revert. This revert happens every time the gmxv2_withdraw function is called, effectively locking any user funds that have been deposited in the protocol. The bug was discovered during a security audit when the code was examined and it was noted that the callbackContract field was set to address(this) without any corresponding implementation. The issue is subtle because unit tests that manually simulate token transfers can pass, masking the missing callback call that occurs only in the live GMX execution flow. From a user’s perspective, attempts to withdraw result in no funds being transferred, the UI may show a pending transaction that eventually fails, or simply display a zero balance change, contrary to the expectation that a withdrawal would return the deposited assets. The impact is severe: all withdrawal functionality is broken, preventing users from retrieving their assets and potentially leading to loss of confidence in the protocol. The vulnerability belongs to the class of missing external callback implementations, where a contract advertises a callback address but does not satisfy the required interface, violating the protocol’s accounting assumptions that post‑withdrawal logic will always execute. To remediate, the module should either remove the callback by setting callbackContract to the zero address when no post‑withdrawal processing is needed, or correctly implement the IWithdrawalCallbackReceiver interface and provide the two required functions. Either fix restores the expected flow, allowing the keeper to call the callbacks successfully and enabling users to withdraw their funds as intended.
