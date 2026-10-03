---
id: 25283
severity: "Low/Info"
---

# The IERC3009 interface is not fully conforming to the standard

## Description

The [IERC3009](<https://github.com/MZero-Labs/common/blob/4a37119f2da946c6d8ad7b9a70dfdd219225115b/src/interfaces/IERC3009.sol>) defines a token interface following the EIP3009 standard. The interface is not fully conforming to the standard and it's missing the following mandatory view functions:

- TRANSFER_WITH_AUTHORIZATION_TYPEHASH
- RECEIVE_WITH_AUTHORIZATION_TYPEHASH Because the interface is also adding the optional canceling functions from EIP3009, it should also be defining the CANCEL_AUTHORIZATION_TYPEHASH view function.

## Proof of Concept

No PoC provided.

## Recommendation

Though the [ERC3009](<https://github.com/MZero-Labs/common/blob/4a37119f2da946c6d8ad7b9a70dfdd219225115b/src/ERC3009.sol>) contract does implement these functions, it is still recommended that the interface implements them as well.
