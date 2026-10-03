---
id: 25178
severity: "Low/Info"
---

# BaseVault is not fully ERC5143 compliant

## Description

The BaseVault implements ERC5143, an extension of ERC4626. Thus, it should try to match every requirement of the ERC. In this case, when setting a new withdraw allowance, an event Approval(address indexed _owner, address indexed _spender, uint256 _value) should be triggered.

Additionally, allowance related functions only let spenders send assets to themselves (unless calling withdrawAllowance related functions).

## Proof of Concept

No PoC provided.

## Recommendation

- Emit the approval event when setting a new withdrawal allowance (when calling approve(...), increaseAllowance(...) and decreaseAllowance(...)).
- Approval related functions should be fully compliant and set the approval of an address to all other addresses. This is important for other dApps to be compatible. Given that borrowing is not part of the standard, the borrow balance could be left as is. However, the withdraw allowance should be turned into the usual allowance mapping of ERC20. Applying the recommended fix to 3S-FUJI-M10 would make this change fully secure.
