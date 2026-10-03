---
id: 25406
severity: "Low/Info"
---

# decimals() is not part of the ERC20 standard and not all tokens may implement it as expected, which may cause initialize() to fail

## Description

BasicVault is initialized by calling asset::decimals(), but as it is not part of the standard, it may not be implement the function in the expected way or at all.

## Proof of Concept

No PoC provided.

## Recommendation

Nothing may be required if the tokens to be integrated all implement the decimals function as is. Alternatively, decimals could be passed as argument.
