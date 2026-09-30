---
id: 7921
severity: "High"
---

# H-1 Contract works with non-existent collections and tokens

## Description

1. View methods (getRoyalties(), tokenURI()) work with non-existent collections. In this example, incorrect royalty is returned for a non-existent collection:
```solidity
await nftContract.getRoyalties(0);
```
returns:
```json
recipients: [
    '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC',
    '0x0000000000000000000000000000000000000000'
],
bps: [
    BigNumber { value: "250" },
    BigNumber { value: "0" }
]
```
2. Athletes and Platform Manager can change parameters for non-existent collections. For example, function updateCollectionAthleteAddress (FantiumNFTV1.sol#L308). 3. A user can try to mint non-existent collections for free via FantiumMinterV1.mint() if maxInvocations is set. (FantiumMinterV1.sol#L241)

## Proof of Concept

no poc

## Recommendation

We recommend checking the existing collectionId and tokenId. An example of classical implementation:
```solidity
require(_exists(tokenId), "Nonexistent token");
```
or
```solidity
function tokenURI(uint256 tokenId) public view virtual override returns (string memory) {
    _requireMinted(tokenId);
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of missing existence validation for collection identifiers and token identifiers in several public view and state‑changing functions. Functions such as getRoyalties and tokenURI accept a collectionId or tokenId without first confirming that the identifier corresponds to a minted collection or token. As a result the contract returns a royalty structure that contains placeholder addresses and zero basis points for collections that have never been created. Likewise, privileged roles (Athlete and Platform Manager) are able to invoke updateCollectionAthleteAddress and similar setters on a collectionId that does not exist, effectively writing arbitrary data into storage slots that are never used by a real collection. In addition, the mint function in FantiumMinterV1 permits a caller to request minting of a collectionId that has not been instantiated; if the maxInvocations field is set, the function bypasses payment checks and mints a token for free. The root cause is the absence of a require(_exists(tokenId)) or similar guard before accessing collection‑specific state. An attacker can exploit this by calling getRoyalties with any arbitrary collectionId to retrieve fabricated royalty data, by altering athlete addresses for phantom collections, or by repeatedly invoking mint with non‑existent collectionIds to obtain free tokens, thereby inflating supply and potentially draining protocol incentives. The impact includes incorrect royalty information being displayed to users, unauthorized modification of collection metadata, and unintended token creation that can distort the economic model, leading to loss of revenue for legitimate creators and confusion for users who see unexpected balances or zero‑value refunds. The bug manifests whenever a function is called with an identifier that has not been minted; it does not require any special permissions beyond those already granted to the caller (any user can call the view functions, and any user can call mint). The issue was discovered during a manual audit that inspected the control flow of collection‑related functions and noted the lack of existence checks. Because the contract still returns syntactically valid data, the problem can be hard to notice unless the caller cross‑checks the collectionId against a registry or observes anomalous royalty payouts. The appropriate remediation is to add explicit existence validation before any read or write of collection‑specific state, for example by invoking _requireMinted(tokenId) or require(collectionExists(collectionId), 'Nonexistent collection') in each affected function. This aligns the contract with the standard pattern for ERC‑721 and ERC‑1155 tokens and restores the invariant that only existing collections can be queried or modified, preventing phantom royalty data, unauthorized parameter changes, and free minting of non‑existent assets.
