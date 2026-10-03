---
id: 25142
severity: "Low/Info"
---

# TroveNFT Duplicates ERC721Enumerable Logic

## Description



## Proof of Concept

## Vulnerability Detail

`ERC721Enumerable` already maintains mappings to track all tokens owned by each address via `_ownedTokens` mapping and provides `tokenOfOwnerByIndex()` function. The custom `_ownerToTroveIds` array duplicates this logic, increasing gas costs and storage usage.

## Impact

Unnecessary gas costs for minting/transferring and storage overhead.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/TroveNFT.sol#L24](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/TroveNFT.sol#L24>)

```solidity
mapping(address => uint256[]) private _ownerToTroveIds;  // @audit - duplicates ERC721Enumerable

function ownerToTroveIds(address owner) external view returns (uint256[] memory) {
    return _ownerToTroveIds[owner];
}
```

ERC721Enumerable already provides: [https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC721/extensions/ERC721Enumerable.sol#L18-L19](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC721/extensions/ERC721Enumerable.sol#L18-L19>)

```solidity
mapping(address => mapping(uint256 => uint256)) private _ownedTokens;
// Can iterate using tokenOfOwnerByIndex(owner, index) for index in [0, balanceOf(owner))
```

## Recommendation

Remove the custom mapping and use ERC721Enumerable's built-in functionality:

```solidity
function ownerToTroveIds(address owner) external view returns (uint256[] memory) {
    uint256 balance = balanceOf(owner);
    uint256[] memory troveIds = new uint256[](balance);
    for (uint256 i = 0; i < balance; i++) {
        troveIds[i] = tokenOfOwnerByIndex(owner, i);
    }
    return troveIds;
}
```
