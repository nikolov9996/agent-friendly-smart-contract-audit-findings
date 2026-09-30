---
id: 18877
severity: "High"
---

# Rounding error in `WUSDA` can result in loss of user funds, especially when manipulated by an attacker

## Description

Due to floor rounding in Solidity, it is possible for rounding errors to affect functions in the `WUSDA` contract.

Specifically, when `WUSDA::_usdaToWUSDA` is invoked internally, if `_usdaAmount` is sufficiently small compared with `MAX_wUSDA_SUPPLY` (10M) and the total USDA supply then it is possible for the `_wusdaAmount` return value to round down to 0.

```solidity
function _usdaToWUSDA(uint256 _usdaAmount, uint256 _totalUsdaSupply) private pure returns (uint256 _wusdaAmount) {
    _wusdaAmount = (_usdaAmount * MAX_wUSDA_SUPPLY) / _totalUsdaSupply;
}
```

When calling the `WUSDA::deposit/depositTo` functions, which call the internal `WUSDA::_deposit` function with this rounded `_wusdaAmount` value, the implication is that depositors could receive little/no WUSDA for their USDA. Additionally, calls to the `WUSDA::withdraw/withdrawTo` functions could be process without actually burning any WUSDA. This is clearly not desirable as USDA can be subsequently redeemed for sUSD (at the expense of the protocol reserves and its other depositors).

```solidity
function deposit(uint256 _usdaAmount) external override returns (uint256 _wusdaAmount) {
    _wusdaAmount = _usdaToWUSDA(_usdaAmount, _usdaSupply());
    _deposit(_msgSender(), _msgSender(), _usdaAmount, _wusdaAmount);
}

function withdraw(uint256 _usdaAmount) external override returns (uint256 _wusdaAmount) {
    _wusdaAmount = _usdaToWUSDA(_usdaAmount, _usdaSupply());
    _withdraw(_msgSender(), _msgSender(), _usdaAmount, _wusdaAmount);
}
```

Even when the USDA supply is sufficiently small to avoid this issue, an attacker could still utilize a sUSD flash loan to artificially inflate the USDA total supply which causes the down rounding, potentially front-running a victim such that their deposit is processed without minting any WUSDA and then withdrawing the inflated USDA supply to repay the flash loan.

## Proof of Concept

_normal case:_

  * Total USDA supply is 10B.
  * Alice calls `WUSDA::deposit` with `_usdaAmount` of 1e23 (10_000 tokens).
  * `_wusdaAmount` is rounded down to 1e20/100 tokens (`1e23 * 1e25 / 1e28 = 1e20`).
  * Alice receives 100 WUSDA rather than 10_000.
  * In reality, the total supply of sUSD is around 40M, so a more realistic scenario assuming 10M total USDA supply may be that Alice deposits 10e18 and receives 1 WUSDA or 1/10th the expected amount (`10e18 * 1e25 / 1e26 = 1e18`).

_flash loan & attacker front-running case:_

  * Total USDA supply is 1M.
  * Alice calls `WUSDA::deposit` with `_usdaAmount` of 9.9e22 (99_000 tokens).
  * Attacker front-runs this transaction and calls `WUSDA::deposit` with `_usdaAmount` of 3.3e22 (33_000 tokens).
  * Attacker receives 33_000 WUSDA.
  * Attacker takes out a sUSD flash loan of 39M.
  * Attacker deposits 39M sUSD into USDA.
  * Alice’s transaction is included here, but `_wusdaAmount` is rounded down to 24_750 tokens (`9.9e22 * 1e25 / 4e25 = 2.475e22`).
  * Alice receives 24_750 WUSDA rather than 99_000 (only 1/4 of the expected amount).
  * Attacker backruns Alice’s transaction and calls `WUSDA::withdraw` with `_usdaAmount` of 132e21 (132_000 tokens).
  * Using the same rounding logic, `_wusdaAmount` is rounded down to 33_000 tokens (`132e21 * 1e25 / 4e25 = 33e22`).
  * Attacker withdraws 132_000 WUSDA and receives the 99_000 USDA deposited by Alice in addition to their original 33_000.
  * Attacker redeems USDA, repays the flash loan and profits 90_000 USDA/sUSD at the expense of Alice.

## Recommendation

Consider reverting if either `WUSDA::_usdaToWUSDA` or `WUSDA::_wUSDAToUSDA` return a zero value. Also consider multiplication by some scalar precision amount. Protections against manipulation of USDA total supply within a single block would also be desirable, perhaps achievable by implementing some multi-block delay.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a rounding error caused by the use of Solidity’s integer division in the conversion routine that maps USDA tokens to wrapped WUSDA tokens. The private function that computes the amount of WUSDA to mint performs a multiplication of the deposited USDA amount by a fixed maximum supply constant and then divides by the total USDA supply, without any additional precision scaling. Because Solidity truncates the result toward zero, when the deposited USDA amount is small relative to the total USDA supply, or when the total supply is artificially inflated within a single block, the division can round down to zero or to a value far smaller than expected. This occurs both in the deposit path, where a user may receive little or no WUSDA for the USDA they supplied, and in the withdraw path, where the contract may attempt to burn zero WUSDA while still releasing USDA, effectively allowing the user to extract value without surrendering the corresponding wrapped tokens. An attacker can exploit this by using a flash loan to temporarily increase the USDA supply, front‑running a victim’s deposit so that the victim’s conversion rounds down to zero, then back‑running a withdraw to capture the victim’s USDA while only burning a minimal amount of WUSDA. The impact is that honest users see their balances unchanged or receive far fewer WUSDA than they paid for, leading to a loss of value that is ultimately absorbed by the protocol’s reserves and other participants. The issue manifests when the contract is called with small deposit amounts, or when the total USDA supply is manipulated in the same block, and it is difficult to notice because the transaction succeeds and emits no error, while the UI may simply show a successful deposit with an unexpectedly low or zero token balance. The bug was discovered during a formal audit by Code4rena through analysis of the conversion formula and testing edge cases where the result could be zero. It belongs to the class of arithmetic precision bugs and rounding‑to‑zero errors that violate the accounting assumptions of a one‑to‑one backing between USDA and WUSDA. To remediate, the contract should check for a zero return from the conversion function and revert, employ a higher‑precision scalar (e.g., using a fixed‑point library) to avoid truncation, and introduce safeguards that prevent the total USDA supply from being altered within a single block, such as a multi‑block delay or snapshot mechanism. These measures would restore the expected economic relationship and protect users from receiving no tokens or losing funds due to rounding.
