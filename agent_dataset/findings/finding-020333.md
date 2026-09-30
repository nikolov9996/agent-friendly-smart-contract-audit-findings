---
id: 20333
severity: "High"
---

# when reservedUntilTokenId > 100 first funder

## Description

The incorrect use of baseTokenId = reservedUntilTokenId may result in the first tokenRecipient[] being invalid, thus preventing the founder from obtaining this portion of the NFT. The current protocol adds a parameter reservedUntilTokenId for reserving Token. This parameter will be used as the starting baseTokenId during initialization.
```solidity
function _addFounders(IManager.FounderParams[] calldata _founders, uint256 reservedUntilTokenId) internal {
    // Used to store the base token id the founder will recieve
    uint256 baseTokenId = reservedUntilTokenId;
    // For each token to vest:
    for (uint256 j; j < founderPct; ++j) {
        // Get the available token id
        baseTokenId = _getNextTokenId(baseTokenId);
        // Store the founder as the recipient
        tokenRecipient[baseTokenId] = newFounder;
        emit MintScheduled(baseTokenId, founderId, newFounder);
        // Update the base token id
        baseTokenId = (baseTokenId + schedule) % 100;
    }
}
```
```solidity
function _getNextTokenId(uint256 _tokenId) internal view returns (uint256) {
    unchecked {
        while (tokenRecipient[_tokenId].wallet != address(0)) {
            _tokenId = (++_tokenId) % 100;
        }
        return _tokenId;
    }
}
```
Because baseTokenId = reservedUntilTokenId is used, if reservedUntilTokenId > 100, for example, reservedUntilTokenId = 200, the first _getNextTokenId(200) will return baseTokenId = 200, tokenRecipient[200] = newFounder. Example: reservedUntilTokenId = 200 founder[0].founderPct = 10 In this way, the tokenRecipient[] of founder will become tokenRecipient[200].wallet = founder (first will call _getNextTokenId(200) return 200) tokenRecipient[10].wallet = founder (second will call _getNextTokenId((200 + 10) %100 = 10)) tokenRecipient[20].wallet = founder ... tokenRecipient[90].wallet = founder However, this tokenRecipient[200] will never be used, because in _isForFounder(), it will be modulo, so only baseTokenId < 100 is valid. In this way, the first founder can actually only 9% of NFT.
```solidity
function _isForFounder(uint256 _tokenId) private returns (bool) {
    // Get the base token id
    uint256 baseTokenId = _tokenId % 100;
    // If there is no scheduled recipient:
    if (tokenRecipient[baseTokenId].wallet == address(0)) {
        return false;
    // Else if the founder is still vesting:
    } else if (block.timestamp < tokenRecipient[baseTokenId].vestExpiry) {
        // Mint the token to the founder
        _mint(tokenRecipient[baseTokenId].wallet, _tokenId);
        return true;
    // Else the founder has finished vesting:
    } else {
        // Remove them from future lookups
        delete tokenRecipient[baseTokenId];
        return false;
    }
}
```
when reservedUntilTokenId > 100 first funder loss 1% NFT

## Proof of Concept

The following test demonstrates that tokenRecipient[200] is for founder.
1. need change tokenRecipient to public, so can assertEq
```solidity
contract TokenStorageV1 is TokenTypesV1 {
    /// @notice The token settings
    Settings internal settings;
    /// @notice The vesting details of a founder
    /// @dev Founder id => Founder
    mapping(uint256 => Founder) internal founder;
    /// @notice The recipient of a token
    /// @dev ERC-721 token id => Founder
    mapping(uint256 => Founder) public tokenRecipient;
}
```
2. add to token.t.sol
```solidity
function test_lossFirst(address _minter, uint256 _reservedUntilTokenId, uint256 _tokenId) public {
    deployAltMock(200);
    (address wallet,) = token.tokenRecipient(200);
    assertEq(wallet,founder);
}
```
$ forge test -vvv --match-test test_lossFirst Running 1 test for test/Token.t.sol:TokenTest [PASS] test_lossFirst(address,uint256,uint256) (runs: 256, : 3221578, ~: 3221578) Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 355.45ms Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests)

## Recommendation

1. A better is that the baseTokenId always starts from 0.
```solidity
function _addFounders(IManager.FounderParams[] calldata _founders, uint256 reservedUntilTokenId) internal {
    // Used to store the base token id the founder will recieve
    uint256 baseTokenId = 0;
```
or
2. use uint256 baseTokenId = reservedUntilTokenId % 100;
```solidity
function _addFounders(IManager.FounderParams[] calldata _founders, uint256 reservedUntilTokenId) internal {
    // Used to store the base token id the founder will recieve
    uint256 baseTokenId = reservedUntilTokenId % 100;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an allocation misalignment caused by using the reservedUntilTokenId value directly as the starting base token identifier when initializing founder vesting schedules. Because the contract later treats token identifiers modulo 100, any reservedUntilTokenId greater than 99 produces a baseTokenId that lies outside the valid range of the tokenRecipient mapping. The first call to _getNextTokenId receives this out‑of‑range identifier, stores the founder in tokenRecipient[200] (for example) but the minting logic in _isForFounder later reduces the token id with %100, so the entry at index 200 is never consulted. As a result the first founder receives one token less than intended (e.g., 9 % instead of 10 %). The root cause is the missing modulo operation when initializing baseTokenId, creating a mismatch between the indexing scheme used for reservation and the indexing scheme used for minting. An attacker or a misconfigured deployment can trigger the condition simply by passing a reservedUntilTokenId value larger than 99, which silently drops the first allocation without reverting. The impact is a loss of ownership of a portion of the NFT for the affected founder, breaking the protocol’s accounting assumptions and potentially reducing the perceived value of the collection. The bug manifests only when the initialization parameter exceeds the 0‑99 range; under normal values the contract behaves as expected. It affects any founder whose allocation is calculated first, as well as downstream users who rely on the correct distribution of tokens. The issue was discovered during a manual audit and confirmed with a unit test that inspected the public tokenRecipient mapping and observed a non‑zero entry at index 200 that never resulted in a minted token. Because the contract never accesses indices above 99 in the minting path, the problem can be hard to notice without explicit inspection of the storage layout. The appropriate fix is to normalize the starting identifier, for example by setting baseTokenId to 0 or by applying a %100 operation to reservedUntilTokenId before the loop, ensuring that all entries written to tokenRecipient are within the range that the minting logic will ever query. This correction restores the intended founder share and aligns the allocation logic with the protocol’s accounting model.
