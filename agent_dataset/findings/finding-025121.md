---
id: 25121
severity: "Crit/High"
---

# Attackers will steal the reserve from the Vault by receiving ra in FlashSwapRouter::__swapDsforRa()

## Description



## Proof of Concept

The following code snippets show how the `Ra` ends up in the `caller`, that is, the user that calls `swapRaforDs()`.

```solidity
function __flashSwap(...) internal {
    ...
    bytes memory data = abi.encode(reserveId, dsId, buyDs, msg.sender, extraData);

    univ2Pair.swap(amount0out, amount1out, address(this), data);
}

function uniswapV2Call(address sender, uint256 amount0, uint256 amount1, bytes calldata data) external {
    (Id reserveId, uint256 dsId, bool buyDs, address caller, uint256 extraData) =
        abi.decode(data, (Id, uint256, bool, address, uint256));
    ...
    if (buyDs) {
        ...
    } else {
        uint256 amount = amount0 == 0 ? amount1 : amount0;

        __afterFlashswapSell(self, amount, reserveId, dsId, caller, extraData);
    }
}

function __afterFlashswapSell(...) internal {
    ...
    IERC20(ra).safeTransfer(caller, raAttributed);
    ...
}
```

## Impact

Users can steal all reserve from the `Vault`.

## Recommendation

The `FlashSwapRouter::__flashSwap()` has to be modified to accept a caller argument, where it accepts either the `msg.sender` or `owner()`. In the flow of selling the reserve, it should send the `Ra` to the `owner`, which is the `Vault`.
