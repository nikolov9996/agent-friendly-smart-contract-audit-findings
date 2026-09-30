---
id: 931
severity: "High"
---

# Index Pool always swap to Zero

## Description

When an Index pool is initiated with two tokens A: B and the weight rate = 1:2, then no user can buy token A with token B.

The root cause is the error in pow. It seems like the dev tries to implement [Exponentiation by squaring](https://en.wikipedia.org/wiki/Exponentiation_by_squaring). [IndexPool.sol#L286-L291](https://github.com/sushiswap/trident/blob/9130b10efaf9c653d74dc7a65bde788ec4b354b5/contracts/pool/IndexPool.sol#L286-L291)

```solidity
function _pow(uint256 a, uint256 n) internal pure returns (uint256 output) {
    output = n % 2 != 0 ? a : BASE;
    for (n /= 2; n != 0; n /= 2) a = a * a;
    if (n % 2 != 0) output = output * a;
}
```

There’s no bracket for `for`.

The `IndexPool` is not functional. I consider this is a high-risk issue.

## Proof of Concept

When we initiated the pool with 2:1.

```solidity
deployed_code = encode_abi(["address[]","uint136[]","uint256"], [
    (link.address, dai.address),
    (2*10**18,  10**18),
    10**13
])
```

No one can buy dai with link.

## Recommendation

The brackets of `for` were missed.

```solidity
function _pow(uint256 a, uint256 n) internal pure returns (uint256 output) {
    output = n % 2 != 0 ? a : BASE;
    for (n /= 2; n != 0; n /= 2) {
        a = a * a;
        if (n % 2 != 0) output = output * a;
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the internal exponentiation routine used by the IndexPool contract to calculate token conversion ratios. The routine, intended to implement exponentiation by squaring, is missing a block delimiter for the for‑loop. As a result, the body of the loop only contains the statement that squares the base (a = a * a), while the conditional that should update the accumulated result (output = output * a) is executed after the loop has terminated, when the loop index n has already been reduced to zero. Consequently, the output variable never incorporates the multiplied terms that arise from the odd‑exponent branches of the algorithm. When the pool is instantiated with a weight configuration where the exponent is even (e.g., a 1:2 weight ratio), the faulty pow function returns a constant base value instead of the correct scaling factor. The pool’s pricing logic therefore computes a zero or negligible effective price for the lower‑weight token, making it impossible for any user to purchase that token with the higher‑weight counterpart. From the user’s perspective, attempts to swap token B for token A appear to succeed on the transaction level, but the received amount of token A is always zero, leaving the user’s balance unchanged and effectively locking the intended trade. This breach of accounting assumptions violates the core business logic that the pool must maintain proportional liquidity according to the declared weights. The issue was discovered during a manual code audit performed by Code4rena, where the missing braces were identified by inspecting the _pow function’s control flow. The problem is subtle because the function compiles without errors and the pool can be deployed, yet the incorrect arithmetic silently disables a whole class of swaps. To remediate the defect, the for‑loop must be wrapped in braces so that the conditional multiplication of the output occurs on each iteration, faithfully reproducing the exponentiation‑by‑squaring algorithm. Restoring the correct arithmetic restores the expected price curve and allows users to acquire the lower‑weight token according to the pool’s weight configuration, thereby re‑establishing proper fund flow and preventing silent loss of functionality.
