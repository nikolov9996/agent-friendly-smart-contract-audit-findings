---
id: 6781
severity: "Critical"
---

# swapOut allows overwrite of token balance

## Description

The StableSwapFacet has the function swapExactOut() where a user could supply the same assetIn address as assetOut, which means the TokenIndexes for tokenIndexFrom and tokenIndexTo function swapOut() are the same.
In function swapOut() a temporay array is used to store balances.
When updating such balances, first self.balances[tokenIndexFrom] is updated and then self.balances[tokenIndexTo] is updated afterwards.
However when tokenIndexFrom == tokenIndexTo the second update overwrites the first update, causing token balances to be arbitrarily lowered. This also skews the exchange rates, allowing for swaps where value can be extracted.
Note: the protection against this problem is location in function getY(). However, this function is not called from swapOut().
Note: the same issue exists in swapInternalOut(), which is called from swapFromLocalAssetIfNeededForExactOut() via _swapAssetOut(). However, via this route it is not possible to specify arbitrary token indexes. Therefore, there isn’t an immediate risk here.
```solidity
contract StableSwapFacet is BaseConnextFacet {
    ...
    function swapExactOut(... ,address assetIn, address assetOut, ... ) ... {
        return
            s.swapStorages[canonicalId].swapOut(
                getSwapTokenIndex(canonicalId, assetIn),
                // assetIn could be same as assetOut
                getSwapTokenIndex(canonicalId, assetOut),
                amountOut,
                maxAmountIn
            );
    }
    ...
}
```
```solidity
library SwapUtils {
    function swapOut(...,
        uint8 tokenIndexFrom, uint8 tokenIndexTo, ... ) ... {
        ...
        uint256[] memory balances = self.balances;
        ...
        self.balances[tokenIndexFrom] = balances[tokenIndexFrom].add(dx).sub(dxAdminFee);
        self.balances[tokenIndexTo] = balances[tokenIndexTo].sub(dy); // overwrites previous update if From==To
        ...
    }

    function getY(..., uint8 tokenIndexFrom, uint8 tokenIndexTo, ... ) ... {
        ...
        require(tokenIndexFrom != tokenIndexTo, "compare token to itself"); // here is the protection
        ...
    }
}
```
Below is a proof of concept which shows that the balances of index 3 can be arbitrarily reduced.
```solidity
//SPDX-License-Identifier: MIT
pragma solidity 0.8.14;
import "hardhat/console.sol";
contract test {
    uint[] balances = new uint[](10);
    function swap(uint8 tokenIndexFrom,uint8 tokenIndexTo,uint dx) public {
        uint dy=dx; // simplified
        uint256[] memory mbalances = balances;
        balances[tokenIndexFrom] = mbalances[tokenIndexFrom] + dx;
        balances[tokenIndexTo] = mbalances[tokenIndexTo] - dy;
    }
    constructor() {
        balances[3] = 100;
        swap(3,3,10);
        console.log(balances[3]); // 90
    }
}
```

## Proof of Concept

no poc

## Recommendation

Add the following to swapExactOut() and swapInternalOut():
```solidity
require(tokenIndexFrom != tokenIndexTo, "compare token to itself");
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the stable‑swap facet of the protocol where the public function swapExactOut (and its internal counterpart swapInternalOut) accepts two token addresses, assetIn and assetOut, without enforcing that they refer to different assets. Internally the function resolves each address to a token index and then calls a library routine swapOut that updates the pool’s internal balance array. The routine first copies the current balances into a temporary memory array, then writes the new balance for tokenIndexFrom, and finally writes the new balance for tokenIndexTo. When the two indexes are identical, the second write overwrites the first one, effectively applying the subtraction step after the addition step on the same balance entry. This results in a net reduction of the token’s recorded balance equal to the amount that was supposed to be transferred out, even though no actual token movement occurs. An attacker can therefore trigger a swap where assetIn equals assetOut, specify any positive amount, and cause the pool’s recorded balance for that token to decrease arbitrarily. Because the exchange rate calculation later reads the corrupted balance, the attacker can also manipulate the price curve to extract additional value from subsequent swaps. The flaw is a classic accounting‑logic error where a self‑overwrite of a state variable is not guarded against; it belongs to the class of “balance overwrite” or “self‑transfer accounting” bugs. The issue manifests whenever a user (or a malicious contract) calls swapExactOut with the same token for both input and output, which is allowed by the public interface. It was discovered during a manual security audit when the auditors noticed that the helper function getY contains a require‑statement preventing identical token indexes, but this check is never invoked from swapOut, leaving the path unprotected. The bug can be hard to spot because the code appears to handle swaps correctly and a same‑token swap might be assumed to be a no‑op, yet the sequential balance updates unintentionally create a loss. From a user’s perspective the transaction appears successful, but the user’s token balance in the pool is reduced (e.g., a balance of 100 becomes 90 after a swap of 10 units with the same token), leading to symptoms such as “my funds disappeared” or “the pool balance is lower than expected”. The affected parties include any liquidity provider or trader interacting with the stable‑swap pool, as well as the protocol that relies on accurate accounting for its invariant. To remediate the issue the contract should enforce tokenIndexFrom != tokenIndexTo before performing the balance updates, either by re‑using the existing check from getY or by adding an explicit require statement in swapExactOut and swapInternalOut. Alternatively, the balance update logic could be rewritten to handle the equal‑index case without double‑writing. Applying the fix restores the invariant, prevents arbitrary balance reduction, and eliminates the avenue for value extraction.
