---
id: 25455
severity: "Low/Info"
---

# Bug in _reversePosition() might lead to future exploits

## Description

In the positionManager library, internal functions to increase, decrease, close or even reverse a position tend to not revert and instead rely on a response system to inform the parent function if the call was successful.

Such system is used in function _reversePosition() which closes and opens a position in the reverse direction, if the traded size is larger that the position's old size. The logic to close and open a new position is presented in the following code segment: (note that some code was omited for simplification)

```solidity
function _reversePosition() internal returns (TradeResponse memory response)
{
    (...)
    closeResponse = _closePosition(...);
    if (closeResponse.makerResult != LimitOrderResult.FILLED) return
```

closeResponse; // line 1047 if (notional.div(leverage) != 0) { // if margin of remaining order is non-zero

```solidity
response = _increasePosition(...);
if (closeResponse.makerResult != LimitOrderResult.FILLED) return
```

response; // [line 1060](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/clearinghouse-libs/PositionManager.sol#L1060>) response = TradeResponse({ position: response.position, exchangedQuote: closeResponse.exchangedQuote + response.exchangedQuote, badDebt: closeResponse.badDebt + response.badDebt,

exchangedSize: closeResponse.exchangedSize + response.exchangedSize, (...) makerResult: response.makerResult

```solidity
});
}
}
```

Here, there is a bug in line 1060, which checks if the call to _closePosition() (which had already been checked on the line 1047) was filled, instead of the call to _increasePosition().

This means that lines 1047 and 1060 are checking the same condition, and if the execution reached line 1060, the condition will always be false, leading to unreachable code in line 1060.

At the moment this bug isn't exploitable, since thankfully the function returns the combination of the close response and the increasePosition response, and uses the makerResult of the increasePosition response (which will be handled correctly by the parent function).

There is however, the possibility that a future change exposes this bug, leading to a severe vulnerability.

## Proof of Concept

No PoC provided.

## Recommendation

Change line 1060 to: if (response.makerResult != LimitOrderResult.FILLED) return response;
