---
id: 19589
severity: "High"
---

# Withdrawals can be frozen by creating null deposits

## Description

It won’t be possible to withdraw any LP token after doing a deposit of $0$ liquidity, leading to withdrawals being effectively freezed.

## Proof of Concept

In `liquidity_lockbox, function withdraw` ```solidity uint64 positionLiquidity = mapPositionAccountLiquidity[positionAddress]; // Check that the token account exists if (positionLiquidity == 0) { revert("No liquidity on a provided token account"); } ```
```

The code checks for the existence of a position via the recorded liquidity. This is a clever idea, as querying a non-existant value from a mapping will return $0$. However, in `deposit`, due to a flawed input validation, it is possible to make positions with $0$ liquidity as the only check being done is for liquidity to not be higher than `type(uint64).max`: `liquidity_lockbox, function _getPositionData` ```solidity // Check that the liquidity is within uint64 bounds if (positionData.liquidity > type(uint64).max) { revert("Liquidity overflow"); } ```
```

As it will pass the input validation inside `_getPositionData`, the only way for such a tx to revert is in the [transfer](https://github.com/code-423n4/2023-12-autonolas/blob/2a095eb1f8359be349d23af67089795fb0be4ed1/lockbox-solana/solidity/liquidity_lockbox.sol#L164)/[mint](https://github.com/code-423n4/2023-12-autonolas/blob/2a095eb1f8359be349d23af67089795fb0be4ed1/lockbox-solana/solidity/liquidity_lockbox.sol#L171), which are low-level calls with no checks for success, as stated in my report `Missing checks for failed calls to the token program will corrupt user's positions`. Due to the reasons above, this deposit with $0$ liquidity will be treated as a valid one and will be stored inside the `mapPositionAccountLiquidity` and `positionAccounts` arrays. If we add the fact that withdrawals are done by looping **LINEARLY** through `positionAccounts`: `liquidity_lockbox, function withdraw` ```solidity function withdraw(uint64 amount) external { address positionAddress = positionAccounts[firstAvailablePositionAccountIndex]; // @audit linear loop ...... uint64 positionLiquidity = mapPositionAccountLiquidity[positionAddress]; // Check that the token account exists if (positionLiquidity == 0) { // @audit it will revert here once it reaches the flawed position revert("No liquidity on a provided token account"); } ...... if (remainder == 0) { // @audit if the liquidity after the orca call is 0, close the position and ++ the index ...... // Increase the first available position account index firstAvailablePositionAccountIndex++; // @audit it won't reach here as the revert above will roll-back the whole tx } }
```

It can be seen that once it encounters such a _“fake”_ deposit with $0$ liquidity provided, it will always revert due to the existence check. As there is no other way to update `firstAvailablePositionAccountIndex` to bypass the flawed position, withdrawals will be completely freezed.

## Recommendation

Just check for the supplied liquidity to not be $0$ in `liquidity_lockbox, function _getPositionData` ```solidity // Check that the liquidity > 0 if (positionData.liquidity == 0) { revert("Liquidity cannot be 0"); } // Check that the liquidity is within uint64 bounds if (positionData.liquidity > type(uint64).max) { revert("Liquidity overflow"); } ```
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract allows a user to create a liquidity position with zero LP tokens because the deposit routine only validates that the supplied liquidity does not exceed the uint64 maximum and does not enforce a lower bound. As a result a mapping entry is written with a liquidity value of 0, which the contract later treats as a valid position identifier. The withdrawal function determines whether a position exists by reading the stored liquidity; a value of 0 is interpreted as “no token account” and triggers a revert with the message No liquidity on a provided token account. Since the contract iterates linearly over all stored positions, encountering the artificially created zero‑liquidity entry causes the entire withdraw transaction to fail and prevents any subsequent positions from being processed. This effectively freezes all withdrawals, leaving users unable to retrieve their LP tokens or any associated funds. The issue manifests when an attacker or any user deliberately makes a deposit of exactly zero liquidity, after which any call to withdraw will revert once the loop reaches that entry. The bug was uncovered during a security audit that examined input validation in the deposit path and the existence check in the withdraw path. It is difficult to spot because a zero value is also the default for unmapped keys, so the code mistakenly conflates an uninitialized entry with a deliberately created empty position. The vulnerability belongs to the class of denial‑of‑service bugs caused by missing lower‑bound checks and improper existence verification. From a user perspective the UI will show a normal balance before the withdraw attempt, but the transaction will revert and the balance will remain unchanged, leading to confusion and the perception that funds have disappeared. The proper fix is to add an explicit check that the deposited liquidity is greater than zero (and optionally to guard the withdrawal loop against zero‑liquidity entries), ensuring that only positions with positive liquidity are recorded and that the existence test correctly distinguishes between absent and intentionally empty positions.
