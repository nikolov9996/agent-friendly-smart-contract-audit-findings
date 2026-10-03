---
id: 25243
severity: "Low/Info"
---

# If statements can be inverted to increase readability

## Description

Inverting if statements can help increase readability and decrease overall code complexity.

## Proof of Concept

No PoC provided.

## Recommendation

Take a look at the following example.

```solidity
function withdraw(uint256 amount) external nonReentrant {
    ... if (toWithdraw > 0) {
```

<code when toWithdraw > 0>

```solidity
}
emit Withdraw(user, totalWithdrawAvaxAmount);
}
```

It can be replaced by

```solidity
function withdraw(uint256 amount) external nonReentrant {
    ... emit Withdraw(user, totalWithdrawAvaxAmount);
    if (toWithdraw <= 0) return;
```

<code when toWithdraw > 0> }
