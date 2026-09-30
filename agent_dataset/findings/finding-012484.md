---
id: 12484
severity: "High"
---

# Rounding Issues In Certain Functions

## Description

Per EIP 4626’s Security Considerations (<https://eips.ethereum.org/EIPS/eip-4626>)

> Finally, ERC-4626 Vault implementers should be aware of the need for specific, opposing rounding directions across the different mutable and view methods, as it is considered most secure to favor the Vault itself during calculations over its users:
> 
>   * If (1) it’s calculating how many shares to issue to a user for a certain amount of the underlying tokens they provide or (2) it’s determining the amount of the underlying tokens to transfer to them for returning a certain amount of shares, it should round _down_.
>   * If (1) it’s calculating the amount of shares a user has to supply to receive a given amount of the underlying tokens or (2) it’s calculating the amount of underlying tokens a user has to provide to receive a certain amount of shares, it should round _up_.
> 

Thus, the result of the `previewMint` and `previewWithdraw` should be rounded up.

Other protocols that integrate with Notional’s fCash wrapper might wrongly assume that the functions handle rounding as per ERC4626 expectation. Thus, it might cause some intergration problem in the future that can lead to wide range of issues for both parties.

## Proof of Concept

The current implementation of `convertToShares` function will round down the number of shares returned due to how solidity handles Integer Division. ERC4626 expects the returned value of `convertToShares` to be rounded down. Thus, this function behaves as expected.

```solidity
function convertToShares(uint256 assets) public view override returns (uint256 shares) {
    uint256 supply = totalSupply();
    if (supply == 0) {
        // Scales assets by the value of a single unit of fCash
        uint256 unitfCashValue = _getPresentValue(uint256(Constants.INTERNAL_TOKEN_PRECISION));
        return (assets * uint256(Constants.INTERNAL_TOKEN_PRECISION)) / unitfCashValue;
    }

    return (assets * totalSupply()) / totalAssets();
}
```

ERC 4626 expects the result returned from `previewWithdraw` function to be rounded up. However, within the `previewWithdraw` function, it calls the `convertToShares` function. Recall earlier that the `convertToShares` function returned a rounded down value, thus `previewWithdraw` will return a rounded down value instead of round up value. Thus, this function does not behave as expected.

```solidity
function previewWithdraw(uint256 assets) public view override returns (uint256 shares) {
    if (hasMatured()) {
        shares = convertToShares(assets);
    } else {
        // If withdrawing non-matured assets, we sell them on the market (i.e. borrow)
        (uint16 currencyId, uint40 maturity) = getDecodedID();
        (shares, /* */, /* */) = NotionalV2.getfCashBorrowFromPrincipal(
            currencyId,
            assets,
            maturity,
            0,
            block.timestamp,
            true
        );
    }
}
```

`previewWithdraw` and `previewMint` functions rely on `NotionalV2.getfCashBorrowFromPrincipal` and `NotionalV2.getDepositFromfCashLend` functions. Due to the nature of time-boxed contest, I was unable to verify if `NotionalV2.getfCashBorrowFromPrincipal` and `NotionalV2.getDepositFromfCashLend` functions return a rounded down or up value. If a rounded down value is returned from these functions, `previewWithdraw` and `previewMint` functions would not behave as expected.

## Recommendation

Ensure that the rounding of vault’s functions behave as expected. Following are the expected rounding direction for each vault function:

  * previewMint(uint256 shares) - Round Up ⬆
  * previewWithdraw(uint256 assets) - Round Up ⬆
  * previewRedeem(uint256 shares) - Round Down ⬇
  * previewDeposit(uint256 assets) - Round Down ⬇
  * convertToAssets(uint256 shares) - Round Down ⬇
  * convertToShares(uint256 assets) - Round Down ⬇

`previewMint` returns the amount of assets that would be deposited to mint specific amount of shares. Thus, the amount of assets must be rounded up, so that the vault won’t be shortchanged.

`previewWithdraw` returns the amount of shares that would be burned to withdraw specific amount of asset. Thus, the amount of shares must to be rounded up, so that the vault won’t be shortchanged.

Following is the OpenZeppelin’s vault implementation for rounding reference:

Alternatively, if such alignment of rounding could not be achieved due to technical limitation, at the minimum, document this limitation in the comment so that the developer performing the integration is aware of this.

Judging this and all duplicate regarding EIP4626 implementation as High Risk. 

EIP4626 is aimed to create a consistent and robust implementation patterns for Tokenized Vaults. A slight deviation from 4626 would broke composability and potentially lead to loss of fund (POC in <https://github.com/code-423n4/2022-06-notional-coop-findings/issues/88> can be an example). It is counterproductive to implement EIP4626 but does not conform to it fully. Especially it does seem that most of the time `deposit` would be successful but not `withdraw`, making it even more dangerous when an immutable consumer application mistakenly used the wfcash contract.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inconsistent rounding strategy in a tokenized vault that implements ERC‑4626. ERC‑4626 defines explicit expectations for how rounding should be applied to each of its view and mutable methods: functions that calculate how many shares to mint or how many shares must be burned for a withdrawal must round **down** to protect the vault, while functions that compute the amount of assets needed to obtain a given number of shares, or the amount of shares required to receive a specified asset amount, must round **up** to protect the user. In the examined contract, the `previewMint` and `previewWithdraw` functions are required to round **up**, but they delegate the core arithmetic to the `convertToShares` helper, which performs a plain integer division and therefore rounds **down**. As a result, the preview values returned to callers are systematically lower than they should be. When a user attempts to redeem shares or withdraw assets, the contract may burn fewer shares or transfer fewer assets than the user expects, effectively short‑changing the vault and potentially leaving the user with an unexpected shortfall. The issue becomes especially pronounced when the vault is integrated with other protocols that assume the ERC‑4626-compliant rounding behavior; those protocols will calculate deposits, withdrawals, or minting amounts based on the incorrect preview values, leading to mismatched balances, failed withdrawals, or stuck funds. The bug was discovered during a formal audit that compared the contract’s arithmetic against the ERC‑4626 specification and identified that `previewWithdraw` returned a value that was rounded down rather than up. Because rounding errors are often off‑by‑one and only affect edge cases where division remainders exist, they can be hard to notice during normal testing—especially when test amounts are multiples of the divisor. The impact can range from minor economic inefficiency to severe fund loss if a user’s withdrawal request is denied or if the vault’s accounting becomes inconsistent, breaking composability with other DeFi components. To remediate the issue, the contract should enforce the correct rounding direction for each ERC‑4626 function: `previewMint` and `previewWithdraw` must explicitly round up (e.g., by adding one before division when a remainder exists), while `previewRedeem`, `previewDeposit`, `convertToAssets`, and `convertToShares` should round down. If technical constraints prevent precise rounding, the contract must clearly document the deviation so that integrators can adjust their expectations. This classifies as a rounding or arithmetic precision bug in a financial smart contract, where the misuse of integer division leads to incorrect accounting and potential loss of user funds.
