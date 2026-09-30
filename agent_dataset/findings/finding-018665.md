---
id: 18665
severity: "High"
---

# Marketplace may call `onERC721Received`

## Description

The contract supports a “push-based” NFT supply, where the price and rate are embedded in the data bytes. This way, the lender doesn’t need to additionally approve the NFT, but can just transfer it directly to the contract. However, since the contract also interacts with the marketplace to buy/sell NFT, it has to prevent the issue where the marketplace also sends data bytes, which might tie 1 NFT with 2 different liens and create divergence.
    
```solidity
function onERC721Received(
    address operator,
    address from,
    uint256 tokenId,
    bytes calldata data
) external returns (bytes4) {
    if (data.length == 64) {
        // @audit marketplace is router so the executor contract might not be whitelisted
        if (registeredMarketplaces[operator]) { 
            /// @dev transfer coming from registeredMarketplaces will go through buyNftFromMarket, where the NFT
            /// is matched with an existing lien (realize PnL) already. If procceds here, this NFT will be tied
            /// with two liens, which creates divergence.
            revert Errors.Unauthorized();
        }
        /// @dev MAX_PRICE and MAX_RATE should each be way below bytes32
        (uint256 price, uint256 rate) = abi.decode(data, (uint256, uint256));
        /// @dev the msg sender is the NFT collection (called by safeTransferFrom's _checkOnERC721Received check)
        _supplyNft(from, msg.sender, tokenId, price, rate);
    }
    return this.onERC721Received.selector;
}
```

The contract prevents it by using the `registeredMarketplaces[]` mapping, where it records the address of the marketplace. This check is explicitly commented in the codebase.

However, this is not enough. The protocol plans to integrate with Reservoir’s Router contract, so only the Router address is whitelisted in `registeredMarketplaces[]`. But the problem is, the address that transfers the NFT is not the Router, but the specific Executor contract, which is not whitelisted.

As a result, the marketplace might bypass this check and create a new lien in `onERC721Received()` during the `buyNftFromMarket()` flow, thus making 2 liens track the same NFT.

## Proof of Concept

Function `_execBuyNftFromMarket()` does a low-level call to the exchange.
    
```solidity
// execute raw order on registered marketplace
bool success;
if (useToken == 0) {
    // use ETH
    // solhint-disable-next-line avoid-low-level-calls
    (success, ) = marketplace.call{value: amount}(tradeData);
} else if (useToken == 1) {
    // use WETH
    weth.deposit{value: amount}();
    weth.approve(marketplace, amount);
    // solhint-disable-next-line avoid-low-level-calls
    (success, ) = marketplace.call(tradeData);
}
```

The contract calls to Reservoir’s router contract, which then calls to a specific module to execute the buy. 

```solidity
function _executeInternal(ExecutionInfo calldata executionInfo) internal {
  address module = executionInfo.module;

  // Ensure the target is a contract
  if (!module.isContract()) {
    revert UnsuccessfulExecution();
  }

  (bool success, ) = module.call{value: executionInfo.value}(executionInfo.data);
  if (!success) {
    revert UnsuccessfulExecution();
  }
}
```

## Recommendation

Consider adding a flag that indicates the contract is in the `buyNftFromMarket()` flow and use it as a check in `onERC721Received()`. For example:
    
```solidity
_marketBuyFlow = 1;
_execBuyNftFromMarket(lien.collection, tokenId, amount, useToken, marketplace, tradeData);
_marketBuyFlow = 0;
```

And in `onERC721Receive()`:
    
```solidity
if (data.length == 64) {
  if(_martketBuyFlow) {
    return this.onERC721Received.selector;
  }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is that the contract's onERC721Received handler can be invoked by a marketplace executor contract that is not listed in the registeredMarketplaces whitelist, allowing the marketplace to supply data bytes and create a second lien for the same NFT during a buy flow. The root cause is that the whitelist only checks the operator address (the contract that calls safeTransferFrom) but the actual NFT transfer is performed by a downstream executor contract invoked through Reservoir's router, which is not whitelisted. Consequently, when the contract purchases an NFT from the market, the router forwards the NFT to the contract via the executor, and the onERC721Received function sees data length 64 and proceeds to decode price and rate and call _supplyNft, thereby tying the NFT to a new lien while an existing lien is already being realized in the same transaction. An attacker or a malicious marketplace can exploit this by crafting a trade that triggers the buyNftFromMarket flow and includes data bytes, causing the contract to register two overlapping liens. The impact is that accounting for the NFT becomes inconsistent: the protocol may think the NFT is collateralized twice, leading to double counting of value, potential liquidation of the same asset twice, or loss of funds when the protocol attempts to settle one lien while the other still references the same token. The condition occurs whenever the contract interacts with a marketplace that uses a router architecture where the final NFT transfer originates from an unregistered executor contract. Users who lend NFTs or rely on correct lien tracking may see their collateral status misrepresented, and the protocol's risk models are violated. The issue was discovered during a code audit that noted the whitelist comment and the mismatch between router and executor addresses. It is subtle because the onERC721Received function is normally trusted to receive NFTs only from approved sources, and the presence of data bytes is a legitimate path for push‑based supply, making the extra check easy to overlook. The proper fix is to add a re‑entrancy‑style guard or flow flag that disables the data‑byte processing when the contract is in the middle of a buyNftFromMarket execution, or to extend the whitelist to include the executor contracts, ensuring that any NFT transfer with data bytes is only allowed from explicitly authorized sources. This class of bug is a whitelist bypass combined with improper handling of callback data, leading to divergent state and double‑lien creation.
