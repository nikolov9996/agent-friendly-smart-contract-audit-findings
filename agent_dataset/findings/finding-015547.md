---
id: 15547
severity: "High"
---

# Incorrect Execution Fee Refund address on Failed Deposits or withdrawals in Strategy Vaults

## Description

The Strategy Vaults within the protocol use a two-step process for handling deposits/withdrawals via GMXv2. A createDeposit() transaction is followed by a callback function (afterDepositExecution() or afterDepositCancellation()) based on the transaction's success. In the event of a failed deposit due to vault health checks, the execution fee refund is mistakenly sent to the depositor instead of the keeper who triggers the deposit failure process.

The protocol handles the deposit through the deposit function, which uses several parameters including an execution fee that refunds any excess fees. 

```solidity
function deposit(GMXTypes.DepositParams memory dp) external payable nonReentrant {
        GMXDeposit.deposit(_store, dp, false);
    }

struct DepositParams {
    // Address of token depositing; can be tokenA, tokenB or lpToken
    address token;
    // Amount of token to deposit in token decimals
    uint256 amt;
    // Minimum amount of shares to receive in 1e18
    uint256 minSharesAmt;
    // Slippage tolerance for adding liquidity; e.g. 3 = 0.03%
    uint256 slippage;
    // Execution fee sent to GMX for adding liquidity
    uint256 executionFee;
  }
```

The refund is intended for the message sender (msg.sender), which in the initial deposit case, is the depositor. This is established in the GMXDeposit.deposit function, where self.refundee is assigned to msg.sender.

```solidity
function deposit(GMXTypes.Store storage self, GMXTypes.DepositParams memory dp, bool isNative) external {
        // Sweep any tokenA/B in vault to the temporary trove for future compouding and to prevent
        // it from being considered as part of depositor's assets
        if (self.tokenA.balanceOf(address(this)) > 0) {
            self.tokenA.safeTransfer(self.trove, self.tokenA.balanceOf(address(this)));
        }
        if (self.tokenB.balanceOf(address(this)) > 0) {
            self.tokenB.safeTransfer(self.trove, self.tokenB.balanceOf(address(this)));
        }

        self.refundee = payable(msg.sender);

		...

		dc.depositKey = GMXManager.addLiquidity(self, alp);

        self.depositCache = _dc;

        emit DepositCreated(dc.user, dc.depositParams.token, _dc.depositParams.amt);
    }
```

If the deposit passes the GMX checks, the afterDepositExecution callback is triggered, leading to vault.processDeposit() to check the vault's health. A failure here updates the status to GMXTypes.Status.Deposit_Failed. The reversal process is then handled by the processDepositFailure function, which can only be called by keepers. They pay for the transaction's gas costs, including the execution fee.

```solidity
function processDepositFailure(uint256 slippage, uint256 executionFee) external payable onlyKeeper {
        GMXDeposit.processDepositFailure(_store, slippage, executionFee);
    }
```

In GMXDeposit.processDepositFailure, self.refundee is not updated, resulting in any excess execution fees being incorrectly sent to the initial depositor, although the keeper paid for it.

```solidity
function processDepositFailure(GMXTypes.Store storage self, uint256 slippage, uint256 executionFee) external {
        GMXChecks.beforeProcessAfterDepositFailureChecks(self);

        GMXTypes.RemoveLiquidityParams memory _rlp;

        // If current LP amount is somehow less or equal to amount before, we do not remove any liquidity
        if (GMXReader.lpAmt(self) <= self.depositCache.healthParams.lpAmtBefore) {
            processDepositFailureLiquidityWithdrawal(self);
        } else {
            // Remove only the newly added LP amount
            _rlp.lpAmt = GMXReader.lpAmt(self) - self.depositCache.healthParams.lpAmtBefore;

            // If delta strategy is Long, remove all in tokenB to make it more
            // efficent to repay tokenB debt as Long strategy only borrows tokenB
            if (self.delta == GMXTypes.Delta.Long) {
                address[] memory _tokenASwapPath = new address[](0);
                _tokenASwapPath[0] = address(self.lpToken);
                rlp.tokenASwapPath = tokenASwapPath;

                (rlp.minTokenAAmt, rlp.minTokenBAmt) = GMXManager.calcMinTokensSlippageAmt(
                    self, _rlp.lpAmt, address(self.tokenB), address(self.tokenB), slippage
                );
            } else {
                (rlp.minTokenAAmt, rlp.minTokenBAmt) = GMXManager.calcMinTokensSlippageAmt(
                    self, _rlp.lpAmt, address(self.tokenA), address(self.tokenB), slippage
                );
            }

            _rlp.executionFee = executionFee;

            // Remove liqudity
            self.depositCache.withdrawKey = GMXManager.removeLiquidity(self, _rlp);
        }
```

The same issue occurs in the processWithdrawFailure function where the excess fees will be sent to the initial user who called withdraw instead of the keeper.

This flaw causes a loss of funds for the keepers, negatively impacting the vaults. Users also inadvertently receive extra fees that are rightfully owed to the keepers

## Proof of Concept

no poc

## Recommendation

The processDepositFailure  and processWithdrawFailure functions must be modified to update self.refundee to the current executor of the function, which, in the case of deposit or withdraw failure, is the keeper.

```solidity
function processDepositFailure(GMXTypes.Store storage self, uint256 slippage, uint256 executionFee) external {
        GMXChecks.beforeProcessAfterDepositFailureChecks(self);

        GMXTypes.RemoveLiquidityParams memory _rlp;

		self.refundee = payable(msg.sender);

		...
        }
```

```solidity
function processWithdrawFailure(
    GMXTypes.Store storage self,
    uint256 slippage,
    uint256 executionFee
  ) external {
    GMXChecks.beforeProcessAfterWithdrawFailureChecks(self);

	self.refundee = payable(msg.sender);

	...
  }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a misdirection of the execution‑fee refund when a deposit or withdrawal in a Strategy Vault fails. The contract stores the address that should receive any leftover execution fee in a variable called refundee. During a normal deposit the refundee is set to the original caller (the depositor) because that caller also pays the fee. However, when the deposit or withdrawal later fails a keeper – an off‑chain actor that monitors the vault – calls a failure‑handling function (processDepositFailure or processWithdrawFailure) and pays the gas for the reversal. The failure‑handling code never updates the refundee variable, so the contract still thinks the original depositor (or withdrawer) is the rightful recipient. Consequently the excess execution fee that the keeper has just spent is sent back to the user instead of the keeper. The root cause is the omission of a self.refundee = payable(msg.sender) assignment in the failure paths, leaving the beneficiary unchanged from the initial deposit call. An attacker does not need to craft special inputs; the bug is triggered automatically whenever a deposit or withdrawal fails the vault‑health check and a keeper invokes the failure function. The impact is a systematic loss of execution‑fee refunds for keepers, which reduces their incentive to monitor the vault and can lead to under‑compensation for the gas they spend. Users may notice an unexpected increase in their balance (a small fee credit) that does not correspond to any action they performed, while keepers see a shortfall in the fee they expected to be reimbursed. The issue occurs only under the specific condition that the deposit or withdrawal fails after the initial liquidity addition, and that the failure is processed by a keeper. It was discovered during a manual audit that traced the flow of the refundee variable through the deposit lifecycle and noticed that it was never reassigned in the failure handlers. The bug is subtle because the refund logic is hidden behind internal calls and only activates on rare failure paths, making it easy to overlook in testing. The vulnerability belongs to the class of incorrect beneficiary assignment or misdirected refund bugs, where a contract sends funds to the wrong party due to stale state. To fix the problem the failure‑handling functions should explicitly set the refundee to the caller (the keeper) before any refund is performed, ensuring that the execution fee is returned to the entity that actually incurred the cost. This change restores the intended accounting logic, aligns incentives, and prevents users from receiving fees that belong to keepers.
