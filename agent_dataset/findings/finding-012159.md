---
id: 12159
severity: "High"
---

# Improper Logic of ERC721Base::_addTokenTo()/_removeTokenFrom()

## Description

The ERC721Base contract implements the standard ERC721 interfaces. Additionally, it implements the enumerability of all token IDs owned by the user.
In particular, mapping(address => uint256[]) internal _userTokens is designed to record all the token IDs held by the user and mapping(uint256 => uint256) internal _indexOfToken records the index of the token inside the user's token array. Meanwhile, the _addTokenTo() and _removeTokenFrom() routines are designed to manage the token IDs held by the user. While examining the related logic, we observe the current implementation should be improved.
To elaborate, we show below the related code snippet of the ERC721Base contract. Inside the _addTokenTo() routine, the statement of _userTokens[_to].push(_tokenId) (line 407) is executed to push the _tokenId to the _to's token array. Subsequently, the statement of _indexOfToken[_tokenId] = _userTokens[_to].length (line 408) is executed to record the index of the _tokenId inside the user's token array. However, it ignores the fact that the index of the array starts from 0.
```solidity
function _addTokenTo(address _to, uint256 _tokenId) internal {
    _tokenOwner[_tokenId] = _to;
    _userTokens[_to].push(_tokenId);
    _indexOfToken[_tokenId] = _userTokens[_to].length;
    _tokensCount = _tokensCount.add(1);
    _userPurchaseDate[_to] = block.timestamp;
}
```
Moreover, by design, the _removeTokenFrom() routine is used to remove the given _tokenId token from the given _from address. In order to meet the requirement, it needs to replace _tokenId with the last token ID inside the _from's token array and update the index of the last token ID. Eventually, the array's last element should be released via pop(). However, it comes to our attention that the current implementation is far from the design.
```solidity
function _removeTokenFrom(address _from, uint256 _tokenId) internal {
    uint256 tokenIndex = _indexOfToken[_tokenId];
    uint256 lastTokenIndex = _userTokens[_from].length.sub(1);
    uint256 lastTokenId = _indexOfToken[lastTokenIndex];
    _userTokens[_from][tokenIndex] = lastTokenId;
    _indexOfToken[lastTokenId] = tokenIndex;
    _userTokens[_from].pop();
    _tokenOwner[_tokenId] = address(0);
    _tokensCount = _tokensCount.sub(1);
    if (_userTokens[_from].length == 0) {
        delete _userTokens[_from];
    }
}
```

## Proof of Concept

no poc

## Recommendation

Correct the implementation of above-mentioned routines as below:
```solidity
function _addTokenTo(address _to, uint256 _tokenId) internal {
    _tokenOwner[_tokenId] = _to;
    _userTokens[_to].push(_tokenId);
    _indexOfToken[_tokenId] = _userTokens[_to].length - 1;
    _tokensCount = _tokensCount.add(1);
    _userPurchaseDate[_to] = block.timestamp;
}

function _removeTokenFrom(address _from, uint256 _tokenId) internal {
    uint256 tokenIndex = _indexOfToken[_tokenId];
    uint256 lastTokenId = _userTokens[_from][_userTokens[_from].length - 1];
    _userTokens[_from][tokenIndex] = lastTokenId;
    delete _indexOfToken[_tokenId];
    _userTokens[_from].pop();
    _tokenOwner[_tokenId] = address(0);
    _tokensCount = _tokensCount.sub(1);
    if (_userTokens[_from].length == 0) {
        delete _userTokens[_from];
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one logic error in the internal bookkeeping of an ERC‑721 implementation that maintains per‑owner token enumeration. The contract stores each owner's token IDs in an array and records the position of each token in a separate index mapping. When a token is added, the code writes the array length to the index mapping, forgetting that array indices start at zero. When a token is removed, the code reads the index of the last token from the index mapping instead of from the array, and it never clears the index entry of the removed token. As a result, the stored index can point past the end of the array and the removal routine can overwrite the wrong slot or leave stale entries. This flaw can be triggered whenever a user receives a token or when a token is transferred away, especially when the owner holds a single token or when tokens are transferred repeatedly. An attacker who can cause a transfer to or from a vulnerable address can cause the enumeration to become inconsistent: the owner's token list may miss a token, show duplicate IDs, or report an incorrect balance. From the user’s point of view the UI may display that a token has disappeared, that the balance shown by balanceOf does not match the list of token IDs, or that a previously owned NFT is no longer visible even though ownership has not been revoked. The issue was discovered during a manual audit of the ERC721Base contract where the logic of _addTokenTo and _removeTokenFrom was examined against the ERC‑721 Enumerable specification. The bug is subtle because the contract still complies with the basic ERC‑721 transfer functions and does not revert; the inconsistency only appears in enumeration queries, making it easy to miss in functional testing. The proper fix is to store the correct zero‑based index when adding a token (length‑1) and to retrieve the last token ID directly from the owner's array, update the index mapping for the moved token, and delete the index entry of the removed token. Aligning the implementation with the ERC‑721 Enumerable standard restores accurate accounting of token ownership and prevents token loss or misleading balance information.
