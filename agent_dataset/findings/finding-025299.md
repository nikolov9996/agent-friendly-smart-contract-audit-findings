---
id: 25299
severity: "Low/Info"
---

# transferFrom in ERC20Extended will always emit an Approval event if the allowance changes

## Description

The [ERC20Extended.transferFrom](<https://github.com/MZero-Labs/common/blob/4a37119f2da946c6d8ad7b9a70dfdd219225115b/src/ERC20Extended.sol#L82-L92>) function is using _approvefor changing allowance, and this internal function always fires up an Approval event.

## Proof of Concept

No PoC provided.

## Recommendation

The token should not be firing this event unless by calling the external ERC20.approve function. Other common implementations (OpenZeppelin, solmate) also don't fire this event when allowance changes due to a transferFrom call.
