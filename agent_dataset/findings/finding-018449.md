---
id: 18449
severity: "High"
---

# The last borrowed asset will not be collateralized and the user may be liquidated due to insufficient collateral

## Description

All leveraged positions are opened by simple recursive borrowing loop (supply collateral → borrow → swap → repeat). The issue here is that the last borrowed asset will not be collateralized.
```solidity
function _borrowLoop(
    address _asset,
    address _quote,
    address _bathTokenAsset,
    address _bathTokenQuote,
    uint256 _amount,
    uint256 _toBorrow
) internal returns (uint256 _bathTokenAmount) {
    // supply collateral
    _bathTokenAmount = _supply(_asset, _bathTokenAsset, _amount);

    // calculate how much is needed to borrow from _maxBorrow amount
    //_toBorrow = (_maxBorrow(_bathTokenQuote).mul(_toBorrow)).div(WAD);
    _toBorrow = wmul(_maxBorrow(_bathTokenQuote), _toBorrow);

    // swap borrowed quote tokens to asset tokens
    _borrow(_bathTokenQuote, _toBorrow);
    _rubiconSwap(_asset, _quote, _toBorrow, true);
}
...
            // increase bathToken amount in order to save it in positions map
            vars.currentBathTokenAmount += _borrowLoop(
                asset,
                quote,
                bathTokenAsset,
                bathTokenQuote,
                vars.currentAssetBalance,
                vars.toBorrow
            );
        }
```

Consider the WBTC collateralization rate is 0.7.

Alice uses 1e8 WBTC and 1.7x leverage to long WBTC

In `_borrowLoop`, 1e8 WBTC is collateralized and borrowed to USDC, and 0.7e8 WBTC is purchased using USDC, and the 0.7e8 WBTC is uncollateralized. At this point, the user’s collateral is 1e8 WBTC and the borrowed USDC is worth 0.7e8 WBTC. If the price of WBTC drops slightly, the user will be liquidated.

The POC below indicates the purchased WBTC is not collateralized:
```solidity
describe("Long positions 📈", function () {
  it("POC1", async function () {
    const { owner, testCoin, testStableCoin, Position } = await loadFixture(
      deployPoolsUtilityFixture
    );
    const TEST_AMOUNT_1 = parseUnits("1");
    const x1_7 = parseUnits("1.7");

    await Position.connect(owner).buyAllAmountWithLeverage(
      testCoin.address,
      testStableCoin.address,
      TEST_AMOUNT_1,
      x1_7
    );

    const position = await Position.positions(1);

    console.log("borrowedAmount1 : %s",position[2]);
    console.log("testCoin balance in position : %s",await testCoin.balanceOf(Position.address));
  });
```
Leverage positions Test  
Pools Utility Test  
Long positions 📈  
borrowedAmount1 : 630000  
testCoin balance in position : 692923770693000000

## Proof of Concept

no poc

## Recommendation

When the loop in `openPosition` ends, collateralize the remaining assets in the contract.
```solidity
            vars.currentBathTokenAmount += _borrowLoop(
                asset,
                quote,
                bathTokenAsset,
                bathTokenQuote,
                vars.currentAssetBalance,
                vars.toBorrow
            );
        }
    }
    vars.currentBathTokenAmount += _supply(asset, bathTokenAsset, IERC20(asset).balanceOf(address(this)));
    /// @dev save total borrow amount of this current position
    vars.borrowedAmount = (borrowBalance(bathTokenQuote)).sub(
        vars.borrowedAmount
    );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way leveraged positions are built through a recursive borrowing loop that repeatedly supplies collateral, borrows a quote asset, swaps it back to the base asset and repeats. In the final iteration of this loop the contract acquires a new amount of the base asset (the “last borrowed asset”) but never calls the internal supply function to register that amount as collateral before the loop terminates. Consequently the protocol’s accounting records the user’s total collateral as only the originally supplied amount, while the borrowed amount is calculated based on the full amount of quote tokens that were taken out. In practice this means that a user who opens a leveraged long position believes they have, for example, 1 WBTC of collateral and 0.7 WBTC worth of borrowed USDC, but the 0.7 WBTC that was purchased with the borrowed USDC is not counted as collateral. If the market price of the base asset drops even slightly, the effective collateralisation ratio falls below the required threshold and the position becomes eligible for liquidation. The impact is that users can lose their deposited funds or be forced to liquidate at unfavorable prices, and the protocol may suffer increased liquidation events that were not anticipated by its risk model. The issue appears only when the open‑position function finishes its borrowing loop; any remaining balance of the base asset held by the contract is left un‑collateralised. It affects any participant who creates leveraged positions using the contract, as well as the protocol’s overall health because the accounting mismatch can trigger unnecessary liquidations. The problem was discovered during a security audit when the auditors observed that after executing a leveraged purchase the contract’s balance of the base token was non‑zero but the internal collateral counter did not reflect this amount. The bug is subtle because the UI may show the correct token balances, yet the internal collateral variable used for liquidation checks is lower than the actual holdings, making the discrepancy hard to spot without inspecting the contract’s state directly. To remediate the issue the contract should, after the borrowing loop ends, explicitly call the supply routine for any residual base‑asset balance held by the contract, thereby updating the collateral accounting before the position is recorded. This ensures that all assets owned by the position are counted as collateral and that the liquidation logic reflects the true risk exposure.
