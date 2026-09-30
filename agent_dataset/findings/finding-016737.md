---
id: 16737
severity: "High"
---

# Add members to the not yet created community

## Description

[Community.sol#L187](https://github.com/code-423n4/2022-08-rigor/blob/main/contracts/Community.sol#L187)  
[Community.sol#L179](https://github.com/code-423n4/2022-08-rigor/blob/main/contracts/Community.sol#L179)  
[Community.sol#L878](https://github.com/code-423n4/2022-08-rigor/blob/main/contracts/Community.sol#L878)  
[SignatureDecoder.sol#L39](https://github.com/code-423n4/2022-08-rigor/blob/main/contracts/libraries/SignatureDecoder.sol#L39)  

There is a `addMember` function in the `Community`. The function accepts `_data` that should be signed by the `_community.owner` and `_newMemberAddr`.

```solidity
// Compute hash from bytes
bytes32 _hash = keccak256(_data);

// Decode params from _data
(
    uint256 _communityID,
    address _newMemberAddr,
    bytes memory _messageHash
) = abi.decode(_data, (uint256, address, bytes));

CommunityStruct storage _community = _communities[_communityID];

// check signatures
checkSignatureValidity(_community.owner, _hash, _signature, 0); // must be community owner
checkSignatureValidity(_newMemberAddr, _hash, _signature, 1); // must be new member
```

The code above shows exactly what the contract logic looks like.

1. `_communityID` is taken from the data provided by user, so it can arbitrarily. Specifically, community with selected `_communityID` can be not yet created. For instance, it can be equal to the `communityCount + 1`, thus the next created community will have this `_communityID`.
2. `_communities[_communityID]` will store null values for all fields, for a selected `_communityID`. That means, `_community.owner == address(0)`
3. `checkSignatureValidity` with a parameters `address(0), _hash, _signature, 0` will not revert a call if an attacker provide incorrect `_signature`.

Let’s see the implementation of `checkSignatureValidity`:

```solidity
// Decode signer
address _recoveredSignature = SignatureDecoder.recoverKey(
    _hash,
    _signature,
    _signatureIndex
);

// Revert if decoded signer does not match expected address
// Or if hash is not approved by the expected address.
require(
    _recoveredSignature == _address || approvedHashes[_address][_hash],
    "Community::invalid signature"
);

// Delete from approvedHash. So that signature cannot be reused.
delete approvedHashes[_address][_hash];
```

No restrictions on `_recoveredSignature` or `_address`. Moreover, if `SignatureDecoder.recoverKey` can return zero value, then there will be no revert.

```solidity
if (messageSignatures.length % 65 != 0) {
    return (address(0));
}

uint8 v;
bytes32 r;
bytes32 s;
(v, r, s) = signatureSplit(messageSignatures, pos);

// If the version is correct return the signer address
if (v != 27 && v != 28) {
    return (address(0));
} else {
    // solium-disable-next-line arg-overflow
    return ecrecover(toEthSignedMessageHash(messageHash), v, r, s);
}
```

As we can see below, `recoverKey` function can return zero value, if an `ecrecover` return zero value or if `v != 27 || v != 28`. Both cases are completely dependent on the input parameters to the function, namely from `signature` that is provided by attacker.

4. `checkSignatureValidity(_newMemberAddr, _hash, _signature, 1)` will not revert the call if an attacker provide correct signature in the function. It is obviously possible.

All in all, an attacker can add as many members as they want, BEFORE the `community` will be created.

## Proof of Concept

no poc

## Recommendation

1. `checkSignatureValidity`/`recoverKey` should revert the call if an `address == 0`.
2. `addMember` should have a `require(_communityId <= communityCount)`

Nice catch!

Btw, this `v != 27 && v != 28` check is no longer needed:

```solidity
if (v != 27 && v != 28) {
    return (address(0));
}
```

See: [https://twitter.com/alexberegszaszi/status/1534461421454606336?s=20&t=H0Dv3ZT2bicx00hLWJk7Fg](https://twitter.com/alexberegszaszi/status/1534461421454606336?s=20&t=H0Dv3ZT2bicx00hLWJk7Fg)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the community membership function that permits the addition of a new member to a community whose identifier has never been instantiated. The root cause is two‑fold: the contract does not verify that the supplied community ID corresponds to an already created community, and the signature‑validation routine treats a zero address as a legitimate signer when the recovered address from the supplied signature is also zero. Because the community storage slot for an uncreated ID contains default zero values, the owner field is address(0). When the addMember logic calls checkSignatureValidity with this zero owner, the internal require statement only fails if the recovered address differs from the expected address and the hash is not pre‑approved. Since recoverKey can return address(0) when the signature’s v value is not 27 or 28, or when ecrecover fails, the condition "_recoveredSignature == _address" evaluates to true (0 == 0) and the call does not revert. Consequently, an attacker can craft a data payload and a matching signature that passes both owner and new‑member checks, even though the community does not exist. By invoking addMember with a community ID equal to communityCount + 1, the attacker can insert arbitrary addresses as members before any official community is created. This mis‑alignment between business logic (a member should only be added to an existing community approved by its owner) and implementation enables a bypass of access control. From a user’s perspective the symptom is that addresses appear as members of a community that has never been set up, potentially granting them rights in later governance or fund‑distribution functions. The impact can range from unauthorized participation in community decisions to the ability to claim rewards or execute privileged actions reserved for members. The issue was discovered during a manual security audit that examined the data decoding and signature verification flow. It may be hard to notice because the contract does not emit explicit events for community creation, and the zero‑address case silently passes the signature check, making the failure mode appear as a normal successful addition. To remediate the problem, the contract should enforce that a community ID is bounded by the current number of created communities (e.g., require(_communityId <= communityCount)) and the signature verification routine should reject a zero address (e.g., revert if _address == address(0) or if _recoveredSignature == address(0)). Additionally, the obsolete v‑value check can be removed, and the overall logic should be tightened to ensure members can only be added after a community is fully initialized.
