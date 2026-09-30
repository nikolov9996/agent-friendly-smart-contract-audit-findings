---
id: 12849
severity: "High"
---

# Zero strike call options can be systemically used to steal premium from the taker

## Description

Some non-malicious ERC20 do not allow for zero amount transfers and order.baseAsset can be such an asset. Zero strike calls are valid and common enough derivative type. However, the zero strike calls with such baseAsset will not be able to be exercised, allowing maker to steal from the taker as a malicious maker can just wait for expiry and withdraw the assets, effectively collecting the premium for free. The premium of zero strike calls are usually substantial.

Marking this as high severity as in such cases malicious maker knowing this specifics can steal from taker the whole premium amount. I.e. such orders will be fully valid for a taker from all perspectives as inability to exercise is a peculiarity of the system which taker in the most cases will not know beforehand.

## Proof of Concept

Currently system do not check the strike value, unconditionally attempting to transfer it:

```solidity
} else {
    ERC20(order.baseAsset).safeTransferFrom(msg.sender, address(this), order.strike);
}
```

As a part of call exercise logic:

```solidity
function exercise(Order memory order, uint256[] calldata floorAssetTokenIds) public payable {
    ...

    if (order.isCall) {
        // -- exercising a call option

        // transfer strike from exerciser to putty
        // handle the case where the taker uses native ETH instead of WETH to pay the strike
        if (weth == order.baseAsset && msg.value > 0) {
            // check enough ETH was sent to cover the strike
            require(msg.value == order.strike, "Incorrect ETH amount sent");

            // convert ETH to WETH
            // we convert the strike ETH to WETH so that the logic in withdraw() works
            // - because withdraw() assumes an ERC20 interface on the base asset.
            IWETH(weth).deposit{value: msg.value}();
        } else {
            ERC20(order.baseAsset).safeTransferFrom(msg.sender, address(this), order.strike);
        }

        // transfer assets from putty to exerciser
        _transferERC20sOut(order.erc20Assets);
        _transferERC721sOut(order.erc721Assets);
        _transferFloorsOut(order.floorTokens, positionFloorAssetTokenIds[uint256(orderHash)]);
    }
}
```

Some tokens do not allow zero amount transfers:

This way for such a token and zero strike option the maker can create short call order, receive the premium:

```solidity
if (weth == order.baseAsset && msg.value > 0) {
    // check enough ETH was sent to cover the premium
    require(msg.value == order.premium, "Incorrect ETH amount sent");

    // convert ETH to WETH and send premium to maker
    // converting to WETH instead of forwarding native ETH to the maker has two benefits;
    // 1) active market makers will mostly be using WETH not native ETH
    // 2) attack surface for re-entrancy is reduced
    IWETH(weth).deposit{value: msg.value}();
    IWETH(weth).transfer(order.maker, msg.value);
} else {
    ERC20(order.baseAsset).safeTransferFrom(msg.sender, order.maker, order.premium);
}
```

Transfer in the assets:

```solidity
// filling short call: transfer assets from maker to contract
if (!order.isLong && order.isCall) {
    _transferERC20sIn(order.erc20Assets, order.maker);
    _transferERC721sIn(order.erc721Assets, order.maker);
    return positionId;
}
```

And wait for expiration, knowing that all attempts to exercise will revert:

```solidity
} else {
    ERC20(order.baseAsset).safeTransferFrom(msg.sender, address(this), order.strike);
}
```

Then recover her assets:

```solidity
// transfer assets from putty to owner if put is exercised or call is expired
if ((order.isCall && !isExercised) || (!order.isCall && isExercised)) {
    _transferERC20sOut(order.erc20Assets);
    _transferERC721sOut(order.erc721Assets);

    // for call options the floor token ids are saved in the long position in fillOrder(),
    // and for put options the floor tokens ids are saved in the short position in exercise()
    uint256 floorPositionId = order.isCall ? longPositionId : uint256(orderHash);
    _transferFloorsOut(order.floorTokens, positionFloorAssetTokenIds[floorPositionId]);

    return;
}
```

## Recommendation

Consider checking that strike is positive before transfer in all the cases, for example:

```solidity
} else {
    if (order.strike > 0) {
        ERC20(order.baseAsset).safeTransferFrom(msg.sender, address(this), order.strike);
    }
}
```

Seems contingent on token implementation, however certain ERC20 do revert on 0 transfer and there would be no way to exercise the contract in that case.

Report: Cannot exercise call contract if strike is 0 and baseAsset reverts on 0 transfers.

There is a pre-requisite for the ERC20 token to revert on 0 amount transfers. However, the warden raised a key point: zero strike calls are common, and their premium is substantial. The information asymmetry of the ERC20 token between the maker and taker is another aggravating factor.

**[outdoteth (Putty Finance) resolved](https://github.com/code-423n4/2022-06-putty-findings/issues/418#issuecomment-1185410362):**

PR with fix: <https://github.com/outdoteth/putty-v2/pull/3>.

**hyh (warden) reviewed mitigation:**

Fixed by conditioning call’s logic on `order.strike > 0`. There is no use case for zero strike puts and so this case remains unconditioned, i.e. still always require successful `order.strike` transfer.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the contract’s exercise logic for call options, which unconditionally attempts to transfer the strike amount from the exerciser to the protocol without first verifying that the strike value is greater than zero. For ERC20 tokens that reject zero‑amount transfers, a call option with a strike of zero becomes impossible to exercise because the transfer step reverts. Zero‑strike call options are a legitimate and frequently used derivative type, and the protocol accepts them as valid orders. A malicious maker can therefore create a short call order with strike = 0 using a base asset that does not allow zero transfers, sell the option to a taker, and collect a substantial premium. When the taker later tries to exercise the option, the contract’s transfer call fails and the transaction reverts, preventing exercise. After the expiry of the option the maker simply withdraws the underlying assets, effectively keeping the premium for free. From the user’s perspective the expectation is that paying a premium grants the right to exercise the call at expiry; instead the taker receives no payout, sees the option marked as expired, and the premium disappears from their balance. The issue is discovered during a security audit that examined the exercise path and identified that the strike value was never validated, leading to a hidden failure mode that only manifests with certain token implementations. It is difficult to notice because the order appears syntactically correct, the contract emits no explicit warning, and zero‑strike calls are common, so a taker may not suspect the underlying token’s transfer behaviour. The class of bug can be described as an unchecked input leading to a conditional revert in asset transfer logic, combined with asymmetrical knowledge of token semantics between maker and taker. To remediate the flaw the contract should enforce that the strike amount is strictly positive before any transfer is attempted, or reject zero‑strike orders entirely, thereby aligning the business logic (exercise requires a payable strike) with the token’s technical constraints and preventing premium theft.
