---
id: 11763
severity: "High"
---

# Some real-world NFT tokens may support both ERC721 and ERC1155 standards, which may break `InfinityExchange::_transferNFTs`

## Description

Many real-world NFT tokens may support both ERC721 and ERC1155 standards, which may break `InfinityExchange::_transferNFTs`, i.e., transferring less tokens than expected.

For example, the asset token of [The Sandbox Game](https://www.sandbox.game/en/), a Top20 ERC1155 token on [Etherscan](https://etherscan.io/tokens-nft1155?sort=7d&order=desc), supports both ERC1155 and ERC721 interfaces. Specifically, any ERC721 token transfer is regarded as an ERC1155 token transfer with only one item transferred ([token address](https://etherscan.io/token/0xa342f5d851e866e18ff98f351f2c6637f4478db5) and [implementation](https://etherscan.io/address/0x7fbf5c9af42a6d146dcc18762f515692cd5f853b#code#F2#L14)).

Assuming there is a user tries to buy two tokens of Sandbox’s ASSETs with the same token id, the actual transferring is carried by `InfinityExchange::_transferNFTs` which first checks ERC721 interface supports and then ERC1155.

```solidity
function _transferNFTs(
  address from,
  address to,
  OrderTypes.OrderItem calldata item
) internal {
  if (IERC165(item.collection).supportsInterface(0x80ac58cd)) {
    _transferERC721s(from, to, item);
  } else if (IERC165(item.collection).supportsInterface(0xd9b67a26)) {
    _transferERC1155s(from, to, item);
  }
}
```

The code will go into `_transferERC721s` instead of `_transferERC1155s`, since the Sandbox’s ASSETs also support ERC721 interface. Then,

```solidity
function _transferERC721s(
  address from,
  address to,
  OrderTypes.OrderItem calldata item
) internal {
  uint256 numTokens = item.tokens.length;
  for (uint256 i = 0; i < numTokens; ) {
    IERC721(item.collection).safeTransferFrom(from, to, item.tokens[i].tokenId);
    unchecked {
      ++i;
    }
  }
}
```

Since the `ERC721(item.collection).safeTransferFrom` is treated as an ERC1155 transferring with one item ([reference](https://etherscan.io/address/0x7fbf5c9af42a6d146dcc18762f515692cd5f853b#code#F2#L833)), there is only one item actually gets transferred.

That means, the user, who barely know the implementation details of his NFTs, will pay the money for two items but just got one.

Note that the situation of combining ERC721 and ERC1155 is prevalent and poses a great vulnerability of the exchange contract.

## Proof of Concept

Check the return values of [Sandbox’s ASSETs](https://etherscan.io/token/0xa342f5d851e866e18ff98f351f2c6637f4478db5)'s `supportInterface`, both `supportInterface(0x80ac58cd)` and `supportInterface(0xd9b67a26)` return true.

## Recommendation

Reorder the checks, e.g.,

```solidity
function _transferNFTs(
  address from,
  address to,
  OrderTypes.OrderItem calldata item
) internal {
  if (IERC165(item.collection).supportsInterface(0xd9b67a26)) {
    _transferERC1155s(from, to, item);
  } else if (IERC165(item.collection).supportsInterface(0x80ac58cd)) {
    _transferERC721s(from, to, item);
  }
}
```

Fixed in <https://github.com/infinitydotxyz/exchange-contracts-v2/commit/377c77f0888fea9ca1e087de701b5384a046f760>.

When an NFT supports both 721 & 1155 interfaces, the code prefers `_transferERC721s` - however this ignores the order’s `numTokens`. This may result in under filling NFTs for an order, at the same cost to the buyer. The warden’s recommendation would address this concern. Or maybe `_transferERC721s` could require `numTokens == 1`, but that approach would be limiting for this scenario. Since the buyer gets a fraction of what they paid for and it impacts a top20 1155, this seems to be a High risk issue.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability stems from the way InfinityExchange determines which transfer routine to invoke for NFT assets. The internal function _transferNFTs first checks whether the token contract reports support for the ERC721 interface (0x80ac58cd) and, if true, calls the ERC721‑specific routine _transferERC721s. Only when the ERC721 check fails does it evaluate support for the ERC1155 interface (0xd9b67a26) and invoke _transferERC1155s. This ordering assumes that a token implements at most one of the two standards. In practice, several real‑world NFT contracts – for example the Sandbox ASSET token – deliberately implement both ERC721 and ERC1155 interfaces so that a single contract can be interacted with using either standard. When such a dual‑standard token is traded on the exchange, the ERC721 check returns true, causing the contract to treat the transfer as an ERC721 operation even though the order was placed as an ERC1155 purchase that expects multiple copies of the same token ID. The ERC721 path iterates over the list of token IDs but transfers each token with a single safeTransferFrom call, ignoring the quantity field that is meaningful for ERC1155. Consequently, a buyer who pays for two copies of an asset receives only one copy, while the full payment is deducted. From the user’s perspective the UI may indicate that the order was fulfilled, yet the wallet balance shows only a single NFT instead of the expected two, leading to confusion and apparent loss of value. The bug is a classic instance of interface detection order causing a wrong code path – a multi‑standard token handling flaw – and it can affect any token that advertises support for both interfaces, not just the Sandbox asset. It was discovered during a security audit that verified the return values of supportsInterface for known top‑20 ERC1155 tokens and observed that both interface identifiers were true. The issue is subtle because the contract compiles and the transfer calls succeed; the problem only becomes visible when the quantity dimension of ERC1155 is exercised. To remediate the vulnerability the contract should prioritize the ERC1155 check before ERC721, or explicitly require that ERC721 transfers only be performed when a single token is requested. This adjustment ensures that orders involving multiple copies are correctly handled, restoring the expected economic behavior and preventing under‑delivery of NFTs.
