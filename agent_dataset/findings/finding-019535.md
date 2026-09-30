---
id: 19535
severity: "High"
---

# Owner cannot withdraw all interest due to wrong calculation of accrued interest in `WithdrawCarry`

## Description

The current `withdrawCarry` function in the contract underestimates the accrued interest due to a miscalculation. This error prevents the rightful owner from withdrawing their accrued interest, effectively locking the assets. The primary issue lies in the calculation of `maximumWithdrawable` within `withdrawCarry`.

## Proof of Concept

**CNOTE Scaling Verification**

An essential aspect of this audit involves verifying the scaling factor of the `CNOTE` exchange rate. The `exchangeRate` scale for `CNOTE` can be verified in the [Canto Network’s GitHub repository](https://github.com/Canto-Network/clm/blob/298377c8711a067a2a49d75a8bf2f90bbbe3de9e/src/CErc20.sol#L15). Evidence confirming that the exponent of the `CNOTE` exchange rate is indeed `18` can be found through [this link to the token tracker](https://tuber.build/token/0xEe602429Ef7eCe0a13e4FfE8dBC16e101049504C?tab=read_proxy). The data provided there shows the current value of the stored exchange rate (`exchangeRateStored`) as approximately `1004161485744613000`. This value corresponds to `1.00416 * 1e18`, reaffirming the `10^18` scaling factor.

This information is critical for accurately understanding the mechanics of CNOTE and ensuring the smart contract’s calculations align with the actual scaling used in the token’s implementation. The verification of this scaling factor supports the recommendations for adjusting the main contract’s calculations and the associated test cases, as previously outlined.

**Testing with Solidity Codes**

Testing with the following Solidity code illustrates the actual `CNOTE` values:

```solidity
function updateBalance() external {
    updatedUnderlyingBalance = ICNoteSimple(cnote).balanceOfUnderlying(msg.sender);
    updatedExchangeRate = ICNoteSimple(cnote).exchangeRateCurrent();

    uint256 balance = IERC20(cnote).balanceOf(msg.sender);
    calculatedUnderlying = balance * updatedExchangeRate / 1e28;
}
```

The corresponding TypeScript logs show a clear discrepancy between the expected and calculated underlying balances:

```javascript
console.log("balanceCnote: ", (Number(balanceCnote) / 1e18).toString());
console.log("exchangeRate: ", Number(exchangeRate).toString());
console.log("underlyingBalance: ", Number(underlyingBalance).toString());
console.log("calculatedUnderlying: ", Number(calculatedUnderlying).toString());
```

With the logs:

```
balanceCnote:  400100.9100006097
exchangeRate:  1004122567006264000
underlyingBalance:  4.017503528113544e+23
calculatedUnderlying:  40175035281135
```

For comprehensive validation, scenario testing using a fork of the mainnet is highly recommended. This approach allows for real-world testing conditions by simulating interactions with existing contracts on the mainnet. It provides a robust environment to verify the correctness and reliability of the contract modifications in real-world scenarios, ensuring that the contract behaves as expected when interfacing with other mainnet contracts.

This step is crucial to identify potential issues that might not be apparent in isolated or simulated environments, enhancing the overall reliability of the contract before deployment.

## Recommendation

**Using `balanceOfUnderlying` Function** - Replace the flawed calculation with the `balanceOfUnderlying` function. This function accurately calculates the underlying `NOTE` balance and is defined in `CToken.sol` ([source](https://github.com/Canto-Network/clm/blob/298377c8711a067a2a49d75a8bf2f90bbbe3de9e/src/CToken.sol#L175)).

**Proposed Code Modifications** - Two alternative implementations are suggested:

1. Without `balanceOfUnderlying`: Modify the scaling factor in the existing calculation from `1e28` to `1e18`.

```solidity
function withdrawCarry(uint256 _amount) external onlyOwner {
    uint256 exchangeRate = CTokenInterface(cNote).exchangeRateCurrent(); // Scaled by 10^18
    // The amount of cNOTE the contract has to hold (based on the current exchange rate which is always increasing) such that it is always possible to receive 1 NOTE when burning 1 asD
    uint256 maximumWithdrawable = (CTokenInterface(cNote).balanceOf(address(this)) * exchangeRate) /
        1e18 -
        totalSupply();
    if (_amount == 0) {
        _amount = maximumWithdrawable;
    } else {
        require(_amount <= maximumWithdrawable, "Too many tokens requested");
    }
    // Technically, _amount can still be 0 at this point, which would make the following two calls unnecessary.
    // But we do not handle this case specifically, as the only consequence is that the owner wastes a bit of gas when there is nothing to withdraw
    uint256 returnCode = CErc20Interface(cNote).redeemUnderlying(_amount);
    require(returnCode == 0, "Error when redeeming"); // 0 on success: https://docs.compound.finance/v2/ctokens/#redeem
    IERC20 note = IERC20(CErc20Interface(cNote).underlying());
    SafeERC20.safeTransfer(note, msg.sender, _amount);
    emit CarryWithdrawal(_amount);
}
```

2. With `balanceOfUnderlying` (Recommended): Utilize the `balanceOfUnderlying` function for a simpler calculation of `maximumWithdrawable`.

```solidity
function withdrawCarry(uint256 _amount) external onlyOwner {
    // The amount of cNOTE the contract has to hold (based on the current exchange rate which is always increasing) such that it is always possible to receive 1 NOTE when burning 1 asD
    uint256 maximumWithdrawable = CTokenInterface(cNote).balanceOfUnderlying(address(this)) - totalSupply();
    if (_amount == 0) {
        _amount = maximumWithdrawable;
    } else {
        require(_amount <= maximumWithdrawable, "Too many tokens requested");
    }
    // Technically, _amount can still be 0 at this point, which would make the following two calls unnecessary.
    // But we do not handle this case specifically, as the only consequence is that the owner wastes a bit of gas when there is nothing to withdraw
    uint256 returnCode = CErc20Interface(cNote).redeemUnderlying(_amount);
    require(returnCode == 0, "Error when redeeming"); // 0 on success: https://docs.compound.finance/v2/ctokens/#redeem
    IERC20 note = IERC20(CErc20Interface(cNote).underlying());
    SafeERC20.safeTransfer(note, msg.sender, _amount);
    emit CarryWithdrawal(_amount);
}
```

The second option is highly recommended for its accuracy and simplicity.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains an arithmetic scaling error in the withdrawCarry function that prevents the contract owner from withdrawing the full amount of accrued interest. The function calculates a variable called maximumWithdrawable by multiplying the contract's cNOTE balance with the current exchange rate and then dividing by a scaling constant. The implementation uses a divisor of 1e28, while the exchange rate for CNOTE is scaled by 1e18. This mismatch causes the computed maximumWithdrawable to be far smaller than the true underlying balance, effectively under‑estimating the interest that should be available for withdrawal. As a result, when the owner calls withdrawCarry – either with a specific amount or with zero to request the maximum – the contract only releases a fraction of the entitled funds, leaving the remainder locked in the contract. From a user perspective the owner sees a withdrawal amount that is unexpectedly low or even zero despite the contract showing a healthy balance, leading to confusion and the impression that funds have disappeared. The bug was discovered during a Code4rena audit when the auditors compared the on‑chain exchangeRate scaling (10^18) with the divisor used in the contract (10^28) and observed a large discrepancy in calculated underlying balances through test logs and manual calculations. The issue is subtle because the contract still executes without reverting, so no explicit error is thrown; the only symptom is the reduced payout, which can be mistaken for normal protocol behavior. This class of vulnerability falls under incorrect unit conversion or decimal precision errors, where a mismatched scaling factor leads to inaccurate financial accounting. The impact is that the protocol’s accounting assumptions are violated – the contract believes it holds sufficient interest to cover withdrawals, but the on‑chain math tells a different story, causing funds to be effectively locked. The bug can be remedied by correcting the scaling divisor from 1e28 to 1e18, or more robustly by replacing the manual calculation with the CToken.balanceOfUnderlying function, which returns the correctly scaled underlying balance and eliminates the need for manual scaling altogether. Implementing the recommended fix restores the ability of the owner to withdraw the full accrued interest and aligns the contract’s accounting with the token’s actual exchange rate semantics.
