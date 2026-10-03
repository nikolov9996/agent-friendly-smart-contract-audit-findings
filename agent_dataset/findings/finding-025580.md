---
id: 25580
severity: "Medium"
---

# Withdrawals and Claims are meant to be pausable, but it is not possible in practice

## Description



## Proof of Concept

The `WithdrawQueue` contract inherits `PausableUpgradable` to provide pausing capabilities to the administrator on users' withdrawals and claims. The contract correctly exposes the `_pause()` and `_unpause()` internal functions through access restricted external functions.

However, none of the functions implement the `whenNotPaused` modifier. This is especially problematic for user-accessible functions: `withdraw` and `claim`.

```solidity
// @POC: WithdrawQueue inherits PausableUpgradeable
contract WithdrawQueue is
    Initializable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    WithdrawQueueStorageV1
{
    // ...

    function initialize(
        IRoleManager _roleManager,
        IRestakeManager _restakeManager,
        IEzEthToken _ezETH,
        IRenzoOracle _renzoOracle,
        uint256 _coolDownPeriod,
        TokenWithdrawBuffer[] calldata _withdrawalBufferTarget
    ) external initializer {

        // ...

        __Pausable_init();

        // ...
    }

    function pause() external onlyWithdrawQueueAdmin {// @POC: pause is accessible to admin
        _pause();
    }

    function unpause() external onlyWithdrawQueueAdmin {// @POC: unpause is accessible to admin
        _unpause();
    }

    function withdraw(uint256 _amount, address _assetOut) external nonReentrant {// @POC: pause has no impact
        // ...
    }

    function claim(uint256 withdrawRequestIndex) external nonReentrant {// @POC: pause has no impact
        // ...
    }
}
```

## Recommendation

Consider implementing `whenNotPaused` modifier on `claim` and `withdraw` functions. The following patch implements such a fix.

```diff
diff --git a/contracts/Withdraw/WithdrawQueue.sol b/contracts/Withdraw/WithdrawQueue.sol
index 786238c..91ec77b 100644
--- a/contracts/Withdraw/WithdrawQueue.sol
+++ b/contracts/Withdraw/WithdrawQueue.sol
@@ -203,7 +203,7 @@ contract WithdrawQueue is
      * @param   _amount  amount of ezETH to withdraw
      * @param   _assetOut  output token to receive on claim
      */
-    function withdraw(uint256 _amount, address _assetOut) external nonReentrant {
+    function withdraw(uint256 _amount, address _assetOut) whenNotPaused external nonReentrant {
         // check for 0 values
         if (_amount == 0 || _assetOut == address(0)) revert InvalidZeroInput();

@@ -276,7 +276,7 @@ contract WithdrawQueue is
      * @dev     revert on claim before cooldown period
      * @param   withdrawRequestIndex  Index of the Withdraw Request user wants to claim
      */
-    function claim(uint256 withdrawRequestIndex) external nonReentrant {
+    function claim(uint256 withdrawRequestIndex) whenNotPaused external nonReentrant {
         // check if provided withdrawRequest Index is valid
         if (withdrawRequestIndex >= withdrawRequests[msg.sender].length)
             revert InvalidWithdrawIndex();
```

*Note: The patch can be applied with `git apply`.*
