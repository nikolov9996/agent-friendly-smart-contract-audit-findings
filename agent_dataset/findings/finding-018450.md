---
id: 18450
severity: "High"
---

# Due to the loss of precision, `openPosition` will make the user’s leverage higher than expected

## Description

`openPosition` creates a leveraged position for the user based on `initMargin` and leverage, and in `_borrowLimit`, it calculates the number of borrowing loops needed to reach the desired amount.
```solidity
(uint256 _assetAmount, uint256 _leverage) {
    (vars.limit, vars.lastBorrow) = _borrowLimit(
        bathTokenAsset,
        asset,
        initMargin,
        leverage
    );
```

For example, if `initMargin` = 1e18 and leverage = 2, then `_desiredAmount` = 2e18. If the collateral factor is 0.7, the user’s position after the first borrowing is 1e18 + 1e18 * 0.7 = 1.7e18, and the user’s position after the second borrowing is 1e18 + 1e18 * 0.7 + 1e18 * 0.7 * 0.7 = 2.19e18.
```solidity
    uint256 _desiredAmount = wmul(_assetAmount, _leverage);

    // check if collateral was already supplied
    uint256 _minted = IERC20(_bathToken).balanceOf(address(this));
    // how much is borrowed on a current loop
    uint256 _loopBorrowed;

    while (_assetAmount <= _desiredAmount) {
        if (_limit == 0) {
            // if collateral already provided
            if (_minted != 0) {
                uint256 _max = _maxBorrow(_bathToken);

                // take into account previous collateral
                _loopBorrowed = wmul(_assetAmount, _collateralFactor).add(
                    _max
                );
            } else {
                _loopBorrowed = wmul(_assetAmount, _collateralFactor);
            }
        } else {
            _loopBorrowed = wmul(_loopBorrowed, _collateralFactor);
        }

        // here _assetAmount refers to the
        // TOTAL asset amount in the position
        _assetAmount += _loopBorrowed;
```

For the excess of 0.19e18, `_lastBorrow` is used as the percentage of the last borrow. It should be noted that when `_lastBorrow` = 0, it means that the percentage of this borrowing is 100%.
```solidity
        if (_assetAmount > _desiredAmount) {
            // in case we've borrowed more than needed
            // return excess and calculate how much is
            // needed to borrow on the last loop
            // to not overflow _desiredAmount
            uint256 _borrowDelta = _desiredAmount.sub(
                _assetAmount.sub(_loopBorrowed)
            );
            _lastBorrow = _borrowDelta.mul(WAD).div(_loopBorrowed);

            _limit++;
            break;
        } else if (_assetAmount == _desiredAmount) {
            // 1x short or perfect matching
            _limit++;
            break;
        } else {
            // default case
            _limit++;
        }
...
        if (i.add(1) == vars.limit && vars.lastBorrow != 0) {
            vars.toBorrow = vars.lastBorrow;
        } else {
            // otherwise borrow max amount available to borrow - 100% from _maxBorrow
            vars.toBorrow = WAD;
        }
```

Although the long leverage must be greater than 1e18, the user can make the long leverage = 1e18+1 to make the long leverage small. But in this case, the loss of precision in the calculation will cause the user to have a higher leverage than expected.
```solidity
    function _leverageCheck(uint256 _leverage, bool _long) internal pure {
        uint256 _wad = WAD;
        uint256 _leverageMax = WAD.mul(3);

        _long // long can't be with 1x leverage
            ? require(
                _leverage > _wad && _leverage <= _leverageMax,
                "_leverageCheck{Long}: INVLAID LEVERAGE"
            )
            : require(
                _leverage >= _wad && _leverage <= _leverageMax,
                "_leverageCheck{Short}: INVLAID LEVERAGE"
            );
    }
```

Consider the following scenario:

The collateral factor of WBTC is 0.7. Alice provides 4e8 WBTC and 1e18+1 long leverage to call the `buyAllAmountWithLeverage` function. Since wmul is rounded rather than rounded up, the `_desiredAmount` calculated in `_borrowLimit` is equal to wmul(4e8,1e18+1) = 4e8.

After that, since `_borrowDelta` == 0, `_borrowLimit` returns limit == 1 and `_lastBorrow` == 0.

Then in `openPosition`, since `_lastBorrow` = 0, borrowing will be done so that Alice’s position reaches 4e8+4e8 * 0.7 = 6.8 WBTC, at which point Alice’s leverage is 1.7e18, much larger than Alice’s expectations, too high leverage will increase the risk of Alice is liquidated.

## Proof of Concept

The POC and output are as follows. It can be seen that the borrowed amount of 1e18+1 is greater than 1.25e18 and 1.337e18, and the actual leverage of 1e18+1 is 1.7e18.
```solidity
describe("Long positions 📈", function () {
  it("POC1", async function () {
    const { owner, testCoin, testStableCoin, Position } = await loadFixture(
      deployPoolsUtilityFixture
    );
    const TEST_AMOUNT_0_4 = parseUnits("0.4");
    const x1_1 = parseUnits("1.000000000000000001");

    await Position.connect(owner).buyAllAmountWithLeverage(
      testCoin.address,
      testStableCoin.address,
      TEST_AMOUNT_0_4,
      x1_1
    );

    const position = await Position.positions(1);

    console.log("borrowedAmount1 : %s",position[2]);
  });

  it("POC2", async function () {
    const { owner, testCoin, testStableCoin, Position } = await loadFixture(
      deployPoolsUtilityFixture
    );
    const TEST_AMOUNT_0_4 = parseUnits("0.4");
    await Position.connect(owner).buyAllAmountWithLeverage(
      testCoin.address,
      testStableCoin.address,
      TEST_AMOUNT_0_4,
      x1_25
    );

    const position = await Position.positions(1);

    console.log("borrowedAmount2 : %s",position[2]);

  });
  it("POC3", async function () {
    const { owner, testCoin, testStableCoin, Position } = await loadFixture(
      deployPoolsUtilityFixture
    );
    const TEST_AMOUNT_0_4 = parseUnits("0.4");
    await Position.connect(owner).buyAllAmountWithLeverage(
      testCoin.address,
      testStableCoin.address,
      TEST_AMOUNT_0_4,
      x1_337
    );

    const position = await Position.positions(1);

    console.log("borrowedAmount3 : %s",position[2]);
  });
```
borrowedAmount1 : 252000  
✓ POC1  
borrowedAmount2 : 90000  
✓ POC2  
borrowedAmount3 : 121320  
✓ POC3

## Recommendation

Consider rounding up in `_borrowLimit` when calculating `_desiredAmount`. Or consider not borrowing when `_lastBorrow` = 0 and modifying the logic of the rest of the code.

It’s true, but leverage values seem too unrealistic to be used in real life (that’s why I disagree with severity). Though, this finding reveals irrelevance of such huge precision for `leverage` param `$`=>`$`. Need to make it less precise.

but leverage values seem too unrealistic to be used in real life

No it isn’t; the warden showed how using a leverage of 1.000000000000000001x ended up using a borrow amount of `252000`, whereas a leverage of 1.25x and 1.337x borrowed smaller amounts of `90000` and `121320` respectively.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract calculates a leveraged long position by multiplying the user’s initial margin with a leverage factor expressed in 18‑decimal fixed‑point (WAD). The multiplication is performed with the helper wmul, which rounds down (floor) instead of rounding up. When a user supplies a leverage value that is only marginally above the minimum (for example 1e18+1, i.e. 1.000000000000000001x), the rounding down causes the computed desired asset amount (_desiredAmount) to be truncated to the same value as the initial margin. Consequently the borrowing loop believes it has not reached the target and proceeds to borrow the full collateral‑factor amount on the first iteration. Because the variable _lastBorrow is set to zero, the contract treats the next loop as a 100 % borrow, resulting in a total position of initial margin plus collateralFactor × initial margin. With a collateral factor of 0.7 this yields a position of 1.7 × initial margin, i.e. an effective leverage of 1.7e18 instead of the requested ~1.000000000000000001x. The bug is triggered only when the leverage is just above the lower bound and the collateral factor is less than one, which makes the loss of precision significant. Users experience a higher‑than‑expected leverage, see a larger borrowed amount than anticipated, and may be liquidated earlier because the protocol assumes a lower risk exposure. The issue was uncovered during a Code4rena audit by constructing test cases that compared borrowed amounts for leverage values of 1.000000000000000001x, 1.25x and 1.337x; the smallest leverage produced the largest borrow due to the rounding error. The problem is hard to notice because the numerical difference is subtle and the contract does not emit explicit warnings about the precision loss. It belongs to the class of fixed‑point rounding bugs that break economic assumptions. To remediate, the calculation of _desiredAmount should round up (or use a ceiling multiplication), the contract should reject leverage values that are too close to the lower bound, or the borrowing logic should avoid a full‑borrow when _lastBorrow equals zero. Reducing the precision of the leverage parameter or adding explicit checks for rounding‑induced over‑leverage would also mitigate the risk.
