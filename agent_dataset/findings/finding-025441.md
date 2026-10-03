---
id: 25441
severity: "Low/Info"
---

# Chain fork changes all obligation Ids, making them unreachable

## Description



## Proof of Concept

## Vulnerability Detail

The obligation id is computed [here](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/libraries/IdLib.sol#L26>) as:

```solidity
function toId(Obligation memory obligation, uint256 chainId, address midnight) internal pure returns (bytes32) {
    return keccak256(
        abi.encodePacked(
            uint8(0xff), midnight, chainId, keccak256(abi.encodePacked(SSTORE2_PREFIX, abi.encode(obligation)))
        )
    );
}
```

After a chain fork, `block.chainid` changes, producing a different id for the same obligation parameters. All storage (positions, collateral, credit, debt, withdrawable) is keyed by the old id, but every function recomputes the id via `toId()`, so the old state is unreachable.

When users interact with the same obligation post-fork, `touchObligation()` creates a brand new obligation with zero state. This does not revert, silently splitting the protocol into an orphaned old obligation (with all the funds) and a fresh new one (with no funds).

This is especially problematic for liquidations, as when it comes back up after a code fix, some positions may be instantly liquidatable due to accrued interest or oracle price changes during the downtime.

## Impact

All funds (loan tokens, collateral) under existing obligations are permanently locked. Lenders lose their credit, borrowers lose their collateral. Very unlikely to happen, and if it does, it should be announced beforehand so the code can be fixed.

## Code Snippet

[https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/libraries/IdLib.sol#L23-L29](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/libraries/IdLib.sol#L23-L29>)

## Recommendation

Remove `chainId` from the id computation, similar to Morpho Blue which does not include it in the market id. Cross-chain replay protection is already handled by the EIP-712 domain separator in the ratifier and authorizer contracts.
