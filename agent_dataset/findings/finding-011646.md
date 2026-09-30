---
id: 11646
severity: "High"
---

# Maker buy order with no specified NFT tokenIds may get fulfilled in `matchOneToManyOrders` without receiving any NFT

## Description

The call stack: matchOneToManyOrders() -> _matchOneMakerSellToManyMakerBuys() -> _execMatchOneMakerSellToManyMakerBuys() -> _execMatchOneToManyOrders() -> _transferMultipleNFTs()

Based on the context, a maker buy order can set `OrderItem.tokens` as an empty array to indicate that they can accept any tokenId in this collection, in that case, `InfinityOrderBookComplication.doTokenIdsIntersect()` will always return `true`.

However, when the system matching a sell order with many buy orders, the `InfinityOrderBookComplication` contract only ensures that the specified tokenIds intersect with the sell order, and the total count of specified tokenIds equals the sell order’s quantity (`makerOrder.constraints[0]`).

This allows any maker buy order with same collection and `empty tokenIds` to be added to `manyMakerOrders` as long as there is another maker buy order with specified tokenIds that matched the sell order’s tokenIds.
```solidity
function canExecMatchOneToMany(
    OrderTypes.MakerOrder calldata makerOrder,
    OrderTypes.MakerOrder[] calldata manyMakerOrders
) external view override returns (bool) {
    uint256 numItems;
    bool isOrdersTimeValid = true;
    bool itemsIntersect = true;
    uint256 ordersLength = manyMakerOrders.length;
    for (uint256 i = 0; i < ordersLength; ) {
        if (!isOrdersTimeValid || !itemsIntersect) {
            return false; // short circuit
        }

        uint256 nftsLength = manyMakerOrders[i].nfts.length;
        for (uint256 j = 0; j < nftsLength; ) {
            numItems += manyMakerOrders[i].nfts[j].tokens.length;
            unchecked {
                ++j;
            }
        }

        isOrdersTimeValid =
            isOrdersTimeValid &&
            manyMakerOrders[i].constraints[3] <= block.timestamp &&
            manyMakerOrders[i].constraints[4] >= block.timestamp;

        itemsIntersect = itemsIntersect && doItemsIntersect(makerOrder.nfts, manyMakerOrders[i].nfts);

        unchecked {
            ++i;
        }
    }

    bool _isTimeValid = isOrdersTimeValid &&
        makerOrder.constraints[3] <= block.timestamp &&
        makerOrder.constraints[4] >= block.timestamp;

    uint256 currentMakerOrderPrice = _getCurrentPrice(makerOrder);
    uint256 sumCurrentOrderPrices = _sumCurrentPrices(manyMakerOrders);

    bool _isPriceValid = false;
    if (makerOrder.isSellOrder) {
        _isPriceValid = sumCurrentOrderPrices >= currentMakerOrderPrice;
    } else {
        _isPriceValid = sumCurrentOrderPrices <= currentMakerOrderPrice;
    }

    return (numItems == makerOrder.constraints[0]) && _isTimeValid && itemsIntersect && _isPriceValid;
}
```

However, because `buy.nfts` is used as `OrderItem` to transfer the nfts from seller to buyer, and there are no tokenIds specified in the matched maker buy order, the buyer wont receive any nft (`_transferERC721s` does nothing, 0 transfers) despite the buyer paid full in price.
```solidity
function _execMatchOneMakerSellToManyMakerBuys(
    bytes32 sellOrderHash,
    bytes32 buyOrderHash,
    OrderTypes.MakerOrder calldata sell,
    OrderTypes.MakerOrder calldata buy,
    uint256 startGasPerOrder,
    uint256 execPrice,
    uint16 protocolFeeBps,
    uint32 wethTransferGasUnits,
    address weth
) internal {
    isUserOrderNonceExecutedOrCancelled[buy.signer][buy.constraints[5]] = true;
    uint256 protocolFee = (protocolFeeBps * execPrice) / 10000;
    uint256 remainingAmount = execPrice - protocolFee;
    _execMatchOneToManyOrders(sell.signer, buy.signer, buy.nfts, buy.execParams[1], remainingAmount);
    _emitMatchEvent(
        sellOrderHash,
        buyOrderHash,
        sell.signer,
        buy.signer,
        buy.execParams[0],
        buy.execParams[1],
        execPrice
    );
}
```
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

## Proof of Concept

1. Alice signed and submitted a maker buy order #1, to buy `2` Punk with `2 WETH` and specified tokenIds = `1`,`2`
2. Bob signed and submitted a maker buy order #2, to buy `1` Punk with `1 WETH` and with no specified tokenIds.
3. Charlie signed and submitted a maker sell order #3, ask for `3 WETH` for `2` Punk and specified tokenIds = `1`,`2`
4. The match executor called `matchOneToManyOrders()` match Charlie’s sell order #3 with buy order #1 and #2, Alice received `2` Punk, Charlie received `3 WETH`, Bob paid `1 WETH` and get nothing in return.

## Recommendation

Change to:
```solidity
function canExecMatchOneToMany(
    OrderTypes.MakerOrder calldata makerOrder,
    OrderTypes.MakerOrder[] calldata manyMakerOrders
) external view override returns (bool) {
    uint256 numItems;
    uint256 numConstructedItems;
    bool isOrdersTimeValid = true;
    bool itemsIntersect = true;
    uint256 ordersLength = manyMakerOrders.length;
    for (uint256 i = 0; i < ordersLength; ) {
        if (!isOrdersTimeValid || !itemsIntersect) {
            return false; // short circuit
        }

        numConstructedItems += manyMakerOrders[i].constraints[0];

        uint256 nftsLength = manyMakerOrders[i].nfts.length;
        for (uint256 j = 0; j < nftsLength; ) {
            numItems += manyMakerOrders[i].nfts[j].tokens.length;
            unchecked {
                ++j;
            }
        }

        isOrdersTimeValid =
            isOrdersTimeValid &&
            manyMakerOrders[i].constraints[3] <= block.timestamp &&
            manyMakerOrders[i].constraints[4] >= block.timestamp;

        itemsIntersect = itemsIntersect && doItemsIntersect(makerOrder.nfts, manyMakerOrders[i].nfts);

        unchecked {
            ++i;
        }
    }

    bool _isTimeValid = isOrdersTimeValid &&
        makerOrder.constraints[3] <= block.timestamp &&
        makerOrder.constraints[4] >= block.timestamp;

    uint256 currentMakerOrderPrice = _getCurrentPrice(makerOrder);
    uint256 sumCurrentOrderPrices = _sumCurrentPrices(manyMakerOrders);

    bool _isPriceValid = false;
    if (makerOrder.isSellOrder) {
        _isPriceValid = sumCurrentOrderPrices >= currentMakerOrderPrice;
    } else {
        _isPriceValid = sumCurrentOrderPrices <= currentMakerOrderPrice;
    }

    return (numItems == makerOrder.constraints[0]) && (numConstructedItems == numItems) && _isTimeValid && itemsIntersect && _isPriceValid;
}
```

Fixed in <https://github.com/infinitydotxyz/exchange-contracts-v2/commit/7f0e195d52165853281b971b8610b27140da6e41>

Confirmed the scenario as described.

Buyers specifying just a collection and no specific tokens is a basically a floor sweep which has become common for NFTs. In this scenario, the warden shows how a buyer can end up spending money and get nothing in return. This is a High risk issue.

Issue [#314](https://github.com/code-423n4/2022-06-infinity-findings/issues/314) is very similar but flips the impact to explore how a seller’s offer could be attacked and how it applies to an allow list of tokenIds. (It has been grouped with H-01)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the order‑matching routine of the Infinity exchange when a maker buy order is created without specifying any token IDs (an empty `tokens` array) to indicate willingness to receive any NFT from a given collection. The matching engine uses `InfinityOrderBookComplication.doTokenIdsIntersect()` which returns true for an empty token list, and the validation logic in `canExecMatchOneToMany` only checks that the total number of token IDs supplied by the collection of buy orders equals the quantity demanded by the sell order. Because the function counts token IDs from all buy orders but does not verify that each individual buy order actually contributes at least one token ID, a buy order with an empty token list can be included in the group as long as another buy order with concrete token IDs satisfies the quantity requirement. When the execution proceeds to `_transferERC721s`, the empty token list results in a loop that performs zero `safeTransferFrom` calls, so the buyer’s funds are transferred to the seller while the buyer receives no NFT. This mismatch between payment and asset delivery constitutes a high‑risk financial loss.

The root cause is a logical omission: the matcher validates only the sum of token IDs (`numItems == makerOrder.constraints[0]`) but does not ensure that the number of constructed items – i.e., the total quantity that will actually be transferred – matches that sum. Consequently, orders that specify “any token” can slip through the validation when paired with other orders that provide the required token IDs. The issue becomes exploitable when an attacker submits a buy order with an empty token list, the protocol matches it together with a legitimate buy order, the price checks succeed, and the attacker’s payment is accepted without any NFT being sent.

The impact is that a user who places a floor‑sweep order (no token IDs) may pay the full price in WETH and see the transaction marked as successful, yet their wallet balance shows a reduction while the owned NFT balance remains unchanged. From the protocol’s perspective, accounting assumptions that each successful match transfers an equal number of NFTs break, potentially leading to inconsistencies in order books and loss of trust. The bug is hard to notice because the matching function returns true and no revert occurs; the transfer loop simply iterates over an empty array, producing no visible error, and the UI may only display that the order was filled.

The vulnerability was discovered during a Code4rena audit using a crafted proof‑of‑concept scenario where three participants (Alice, Bob, Charlie) demonstrated that Bob’s empty‑token buy order resulted in a payment of 1 WETH with zero NFT receipt. The problem belongs to the class of validation bypass bugs caused by improper handling of empty inputs in complex matching algorithms. To remediate, the matcher must track the number of items that will actually be transferred (`numConstructedItems`) and require that this count matches both the seller’s requested quantity and the sum of token IDs supplied by the buy orders. The corrected implementation adds an additional equality check `(numConstructedItems == numItems)` and ensures that each buy order contributes concrete token IDs, thereby preventing empty‑token orders from being fulfilled without delivering assets.
