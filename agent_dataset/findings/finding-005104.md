---
id: 5104
severity: "High"
---

# Invalid RLP encoding causes proof veriﬁcation failures for values with leading zeros

## Description

The Prover contract incorrectly prepends ﬁxed-length RLP encoding preﬁxes to values being proven, causing proof veriﬁcation to fail when values contain leading zeros. This affects both L2 state root veriﬁcation and reward claiming, potentially leaving funds permanently stuck if a claimant's address contains leading zeros. In the proveStorage() function, the contract uses ﬁxed-length preﬁxes (e.g., 0xa0, 0x94) when encoding values for RLP veriﬁcation:
```solidity
proveStorage(
    abi.encodePacked(messageMappingSlot),
    bytes.concat(hex"94", bytes20(claimant)), // Fixed 0x94 prefix
    l2StorageProof,
    bytes32(inboxStateRoot)
);
```
However, RLP encoding requires dynamic length preﬁxes that depend on both the length and content of the value being encoded. When a value contains leading zeros, using a ﬁxed-length preﬁx causes the proof veriﬁcation to fail because:
1. The ﬁxed preﬁx incorrectly indicates a speciﬁc length regardless of leading zeros.
2. The actual value's encoding should strip leading zeros and use a preﬁx based on the resulting length.
3. The mismatch between the encoded value and its merkle proof causes veriﬁcation to fail.
The issue manifests in three scenarios:
1. L2 state root veriﬁcation -- If roots contain leading zeros, proofs will fail until a root without leading zeros is available.
2. Reward claiming -- If a claimant's address contains leading zeros, their rewards become permanently unclaimable.
3. Game type encoding:
    • For the default CANNON game type (0), the code uses a 24-byte encoding.
    • The length preﬁx then depends on the timestamp value.
    • When the timestamp exceeds 232 (around February 2106), this encoding will break.
Impact: The impact can be high for affected cases:
    • Claimants with addresses containing leading zeros will be unable to claim their rewards permanently.
    • Bedrock proofs will fail if the outputRoot contains leading zeros.
    • Cannon proofs will fail if the rootClaim contains leading zeros.
    • Cannon proofs will break in 2106 when timestamps exceed 32 bits.
For L2 state root veriﬁcation, failures could delay proof veriﬁcation beyond timeouts, disrupting the protocol's operation. Likelihood: The likelihood of encountering this issue is moderate:
    • Claimant addresses have a 1/256 chance (~0.4%) of containing leading zeros.
    • Bedrock world state proofs have a 1/256 chance of failure when the outputRoot contains leading zeros.
    • Cannon proofs have a 1/256 chance of failure when rootClaim contains leading zeros.
    • The issue is guaranteed to affect all proofs after February 2106 due to the changed length preﬁx of the encoded game ID.

## Proof of Concept

```solidity
it('unable to verify SLOT3 with fixed length prefix', async () => {
    const slot = 3
    const { key, value, proof, hash } = await getStorageProof(storage, slot)
    const lengthPrefix = '0xa0'
    const valueRlp = lengthPrefix + zeroPadValue(toBeHex(value), 32).slice(2)
    expect(value).to.eq('0x407ef388ae4cde1f592306c95')
    expect(valueRlp).to.eq(
        '0xa0000000000000000000000000000000000000000407ef388ae4cde1f592306c95',
    )
    const valid = await verifyStorageProof(prover, key, valueRlp, proof, hash)
    expect(valid).to.be.false
})
```

## Recommendation

Replace ﬁxed-length preﬁx concatenation with proper RLP encoding using RLPWriter.writeUint():
```solidity
- bytes.concat(hex"94", bytes20(claimant))
+ RLPWriter.writeUint(uint160(claimant))
```
This ensures values are correctly RLP encoded with dynamic length preﬁxes that handle leading zeros properly. The change should be made everywhere proveStorage() is called with manually constructed RLP values. Note that only RLPWriter.writeUint() strips leading zeros from the encoded value. RLPWriter.writeBytes() and RLPWriter.writeAddress() should not be used.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect RLP encoding implementation in the Prover contract. The contract builds the RLP representation of values by concatenating a fixed‑length prefix (for example 0x94 for an address) with the raw bytes of the value. RLP, however, requires the length prefix to be calculated from the actual length of the encoded value after stripping any leading zero bytes. When a value such as an address or a state root contains leading zeros, the static prefix advertises a length that does not match the real encoded payload. This mismatch causes the Merkle‑proof verification performed in proveStorage() to reject the proof. The bug appears in three contexts: verification of L2 state roots, reward claiming where the claimant address may have leading zeros, and encoding of the Cannon game type where a timestamp larger than 2^32 changes the required length prefix. An attacker or an unlucky user does not need to craft any malicious transaction; the failure is triggered automatically whenever the data to be proved includes leading zeros. From the user’s perspective the protocol appears to freeze: a claimant sees that their reward balance stays at zero even though the contract records a pending reward, and the UI shows no error message, only the absence of the expected funds. The protocol may also experience time‑outs because proofs that should succeed keep failing, potentially halting the roll‑up finalisation process. The issue was discovered during a manual audit when a test case that forced a value with leading zeros produced a false verification result. Because leading zeros occur only about one in 256 cases, the problem is easy to miss in routine testing and may only surface sporadically, making it hard to reproduce. The proper fix is to replace the manual prefix concatenation with a correct RLP encoder that generates dynamic length prefixes, such as RLPWriter.writeUint for numeric values or the appropriate RLPWriter function for addresses, ensuring that leading zeros are stripped before the prefix is applied. By using a standards‑compliant RLP encoding the proof verification will succeed regardless of the value’s byte pattern, restoring the ability of users to claim rewards and allowing the protocol to process state roots reliably.
