---
id: 4979
severity: "High"
---

# Incorrect ft reserve used in _buyToken leads to incorrect ft calculation and completely breaks protocol logic Submitted by BengalCatBalu, also found by 0xtincion

## Description

Impact Explanation:
• First, if ftReserves < netOut + feeAmt - unnecessary debt will be taken on the user (_issueFt takes
new ft in gt).
• Second - _issueFtToSelf updates transientStorage at the end of execution, indicating the current
balance of the contract - but this balance is not balanceOf, but targetFtReserve - that is, an invalid
value.
```solidity
function _issueFtToSelf(uint256 ftReserve, uint256 targetFtReserve, OrderConfig memory config) internal {
    if (config.gtId == 0) revert CantNotIssueFtWithoutGt();
    uint256 ftAmtToIssue = ((targetFtReserve - ftReserve) * Constants.DECIMAL_BASE)
        / (Constants.DECIMAL_BASE - market.issueFtFeeRatio());
    market.issueFtByExistedGt(address(this), (ftAmtToIssue).toUint128(), config.gtId);
    setTransientFtReserve(targetFtReserve);
}
```
An invalid value in tstore will further cause the invalid value to be passed to the callback - at least this is
bad because this callback is used in Vault and Vault performs its calculations depending on deltaFt.
```solidity
if (address(_orderConfig.swapTrigger) != address(0)) {
    int256 deltaFt = ft.balanceOf(address(this)).toInt256() - getTransientFtReserve().toInt256();
    int256 deltaXt = xt.balanceOf(address(this)).toInt256() - getTransientXtReserve().toInt256();
    _orderConfig.swapTrigger.swapCallback(deltaFt, deltaXt);
}
```

## Proof of Concept

To see that the values are indeed incorrect, paste these two debug outputs into this location in the _buyToken function:
```solidity
if (tokenOut == ft) {
    uint256 ftReserve = getTransientFtReserve();
    console.log("Reserves", ftReserve);
    console.log("Real Balance", ft.balanceOf(address(this)));
    console.log("HERE 4");
    if (ftReserve < netOut + feeAmt) _issueFtToSelf(ftReserve, netOut + feeAmt, config);
}
```
And then run the tests forge test --mt testSellFt -vv:
Recomendation:
```solidity
if (tokenOut == ft) {
    uint256 ftReserve = getTransientFtReserve();
    console.log("Reserves", ftReserve);
    console.log("Real Balance", ft.balanceOf(address(this)));
    console.log("HERE 4");
    if (ftReserve < netOut + feeAmt) _issueFtToSelf(ftReserve, netOut + feeAmt, config);
}
market.mint(address(this), debtTokenAmtIn);
```

## Recommendation

No data

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect handling of the temporary reserve value that the contract stores during a token purchase operation. When a user initiates a buy where the output token is the protocol’s ft token, the function _buyToken reads a transient reserve (ftReserve) and compares it with the amount that should be delivered (netOut plus feeAmt). If the stored reserve is lower than the required amount, the contract calls _issueFtToSelf to mint additional ft tokens. Inside _issueFtToSelf the contract calculates how many ft tokens to issue based on the difference between a target reserve (the amount that should exist after minting) and the current transient reserve, then it mints the tokens and finally writes the target reserve back into transient storage via setTransientFtReserve. The critical mistake is that the transient reserve is overwritten with the target value rather than the actual token balance after minting. Subsequent logic, especially the swap callback used by the Vault, computes a delta value as the on‑chain ft balance minus the stored transient reserve. Because the stored value no longer reflects the real balance, the delta calculation becomes incorrect – often reporting a zero or negative change when a positive change actually occurred. This corrupted delta is then fed into the Vault’s accounting, causing it to believe that either no ft was transferred or that an unexpected debt was created. From a user’s perspective the protocol may appear to give no tokens, to return an unexpectedly small amount, or to charge an unexplained fee, while the internal accounting shows a phantom debt. The issue is triggered only during the specific execution path where tokenOut equals ft and the transient reserve is insufficient, which makes it easy to miss during casual testing because the contract’s external balance looks correct. It was discovered during a focused audit by BengalCatBalu and 0xtincion and reported by Spearbit. The bug belongs to the class of “incorrect internal state tracking” or “reserve accounting mismatch” bugs, where a contract stores a derived value that diverges from the true on‑chain state, leading to downstream miscalculations. To remediate the problem the contract should update the transient reserve with the actual ft balance after issuance, or avoid using a target reserve as a proxy altogether. The callback should base its delta on the real balance, ensuring that the Vault’s accounting remains consistent with the protocol’s economic model.
