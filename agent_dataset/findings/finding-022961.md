---
id: 22961
severity: "High"
---

# Valor._doValorEmission() should not be a pub-

## Description

The Valor._doValorEmission() function is public, meaning it can be called by anyone. If _doValorEmission() is invoked outside of the Staking.updateValorVars() function, it can lead to the accValorPerShareScaled value being incorrectly updated when updateValorVars() is subsequently called. The _doValorEmission() function updates totalValorEmitted and lastValorUpdateTimestamp. However, since _doValorEmission() is a public function, it can be called by anyone, which could lead to unintended updates to these values. https://github.com/OrderlyNetwork/omnichain-ledger/tree/fb0c093da7876968794f6b3a93adcc23b2f81077/omnichain-ledger/contracts/lib/Valor.sol#L127-L133
```solidity
function _doValorEmission() public whenNotPaused returns (uint256 valorEmitted) {
    valorEmitted = _getValorPendingEmission();
    if (valorEmitted > 0) {
        totalValorEmitted += valorEmitted;
        lastValorUpdateTimestamp = block.timestamp;
    }
}
```
If _doValorEmission() is called outside of the Staking.updateValorVars() function, it can affect the calculation of accValorPerShareScaled, potentially leading to incorrect updates to this value. https://github.com/OrderlyNetwork/omnichain-ledger/tree/fb0c093da7876968794f6b3a93adcc23b2f81077/omnichain-ledger/contracts/lib/Staking.sol#L114-L119
```solidity
function updateValorVars() public whenNotPaused {
    uint256 valorEmission = _doValorEmission();
    if (valorEmission > 0) {
        accValorPerShareScaled = _getCurrentAccValorPerShareScaled(valorEmission);
    }
}
```
A malicious user could exploit the interplay between the _doValorEmission() and updateValorVars() functions to indefinitely prevent the growth of accValorPerShareScaled. This could be done by calling _doValorEmission() immediately before updateValorVars() is invoked, which occurs every time staking balances change. Such an attack would lead to users receiving substantially less VALOR tokens than anticipated. Users may receive significantly less VALOR tokens than they expect.

## Proof of Concept

no poc

## Recommendation

The Valor._doValorEmission() function should be a internal function.
```solidity
function _doValorEmission() internal whenNotPaused returns (uint256 valorEmitted) {
    valorEmitted = _getValorPendingEmission();
    if (valorEmitted > 0) {
        totalValorEmitted += valorEmitted;
        lastValorUpdateTimestamp = block.timestamp;
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an improper access control issue where the function that performs the core accounting of VALOR token emission, _doValorEmission, is declared as public instead of internal. This function updates the total amount of VALOR emitted and the timestamp of the last emission, values that are later used by the updateValorVars function to calculate the accumulated reward per share (accValorPerShareScaled). Because the function is publicly callable, any external address can invoke it at arbitrary times. When an attacker calls _doValorEmission immediately before a legitimate call to updateValorVars – which is automatically triggered on every staking balance change – the pending emission is consumed and the internal counters are advanced, causing the subsequent calculation of accValorPerShareScaled to see zero new emission. Repeating this front‑running pattern can indefinitely prevent the growth of accValorPerShareScaled, meaning that stakers receive far fewer VALOR tokens than the protocol’s economics promise. The issue manifests whenever staking activity triggers updateValorVars and a malicious actor can submit a transaction that calls _doValorEmission just before it. The affected parties are all users who stake VALOR, the protocol’s reward distribution mechanism, and any downstream contracts that rely on correct reward accounting. The flaw was discovered during a manual audit that examined function visibility and the interaction between emission and reward‑per‑share calculations; it is subtle because the public function only modifies internal bookkeeping variables and does not emit events or transfer tokens, so the discrepancy may be attributed to normal market fluctuations rather than a contract bug. The bug belongs to the class of “exposed internal accounting function” or “improper visibility” vulnerabilities, where a function intended for internal state updates is mistakenly made externally accessible, allowing state manipulation that breaks business logic. From a user’s perspective the symptoms are a noticeably lower reward accrual, sometimes even zero new VALOR tokens after a claim, and a mismatch between expected and actual balances. The expected behavior is that each staking action increases accValorPerShareScaled proportionally to the pending emission, but the reality under attack is that the reward growth stalls. The recommended remediation is to change the visibility of _doValorEmission to internal (or private) so that only the contract’s own updateValorVars function can invoke it, optionally adding additional access controls or modifiers to ensure the emission logic cannot be triggered externally. This restores the integrity of the reward calculation and aligns the contract’s accounting with its intended economic model.
