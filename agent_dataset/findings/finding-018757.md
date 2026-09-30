---
id: 18757
severity: "High"
---

# Each Well is responsible for ensuring that an `update` call cannot be made with a reserve of 0

## Description

The current implementation of `GeoEmaAndCumSmaPump` assumes each well will call `update()` with non-zero reserves, as commented at the beginning of the file:
```solidity
/**
 * @title GeoEmaAndCumSmaPump
 * @author Publius
 * @notice Stores a geometric EMA and cumulative geometric SMA for each reserve.
 * @dev A Pump designed for use in Beanstalk with 2 tokens.
 *
 * This Pump has 3 main features:
 *  1. Multi-block MEV resistence reserves
 *  2. MEV-resistant Geometric EMA intended for instantaneous reserve queries
 *  3. MEV-resistant Cumulative Geometric intended for SMA reserve queries
 *
 * Note: If an `update` call is made with a reserve of 0, the Geometric mean oracles will be set to 0.
 * Each Well is responsible for ensuring that an `update` call cannot be made with a reserve of 0.
 */
```

However, there is no actual requirement in `Well` to enforce pump updates with valid reserve values. Given that `GeoEmaAndCumSmaPump` restricts values to a minimum of 1 to prevent issues with the geometric mean, that the TWA values are not truly representative of the reserves in the Well, we believe it is worse than reverting in this case, although a `ConstantProduct2` Well can have zero reserves for either token via valid transactions.
```solidity
for (uint i; i < length; ++i) {
    // Use a minimum of 1 for reserve. Geometric means will be set to 0 if a reserve is 0.
    b.lastReserves[i] =
        _capReserve(b.lastReserves[i], (reserves[i] > 0 ? reserves[i] : 1).fromUIntToLog2(), blocksPassed);
    b.emaReserves[i] = b.lastReserves[i].mul((ABDKMathQuad.ONE.sub(aN))).add(b.emaReserves[i].mul(aN));
    b.cumulativeReserves[i] = b.cumulativeReserves[i].add(b.lastReserves[i].mul(deltaTimestampBytes));
}
```

Updating pumps with zero reserve values can lead to the distortion of critical states likely to be utilized for price oracles. Given that the issue is exploitable through valid transactions, we assess the severity as HIGH. It is crucial to note that attackers can exploit this vulnerability to manipulate the price oracle.

## Proof of Concept

The test below shows that it is possible for reserves to be zero through valid transactions and updating pumps do not revert.
```solidity
function testUpdateCalledWithZero() public {
    address msgSender = 0x83a740c22a319FBEe5F2FaD0E8Cd0053dC711a1A;
    changePrank(msgSender);
    IERC20[] memory mockTokens = well.tokens();

    // add liquidity 1 on each side
    uint amount = 1;
    MockToken(address(mockTokens[0])).mint(msgSender, 1);
    MockToken(address(mockTokens[1])).mint(msgSender, 1);
    MockToken(address(mockTokens[0])).approve(address(well), amount);
    MockToken(address(mockTokens[1])).approve(address(well), amount);
    uint[] memory tokenAmountsIn = new uint[](2);
    tokenAmountsIn[0] = amount;
    tokenAmountsIn[1] = amount;
    uint minLpAmountOut = well.getAddLiquidityOut(tokenAmountsIn);
    well.addLiquidity(
        tokenAmountsIn,
        minLpAmountOut,
        msgSender,
        block.timestamp
    );

    // swaFromFeeOnTransfer from token1 to token0
    msgSender = 0xfFfFFffFffffFFffFffFFFFFFfFFFfFfFFfFfFfD;
    changePrank(msgSender);
    amount = 79_228_162_514_264_337_593_543_950_334;
    MockToken(address(mockTokens[1])).mint(msgSender, amount);
    MockToken(address(mockTokens[1])).approve(address(well), amount);
    uint minAmountOut = well.getSwapOut(
        mockTokens[1],
        mockTokens[0],
        amount
    );

    well.swapFromFeeOnTransfer(
        mockTokens[1],
        mockTokens[0],
        amount,
        minAmountOut,
        msgSender,
        block.timestamp
    );
    increaseTime(120);

    // remove liquidity one token
    msgSender = address(this);
    changePrank(msgSender);
    amount = 999_999_999_999_999_999_999_999_999;
    uint minTokenAmountOut = well.getRemoveLiquidityOneTokenOut(
        amount,
        mockTokens[1]
    );
    well.removeLiquidityOneToken(
        amount,
        mockTokens[1],
        minTokenAmountOut,
        msgSender,
        block.timestamp
    );

    msgSender = address(12_345_678);
    changePrank(msgSender);

    vm.warp(block.timestamp + 1);
    amount = 1;
    MockToken(address(mockTokens[0])).mint(msgSender, amount);
    MockToken(address(mockTokens[0])).approve(address(well), amount);
    uint amountOut = well.getSwapOut(mockTokens[0], mockTokens[1], amount);

    uint[] memory reserves = well.getReserves();
    assertEq(reserves[1], 0);

    // we are calling `_update` with reserves of 0, this should fail
    well.swapFrom(
        mockTokens[0],
        mockTokens[1],
        amount,
        amountOut,
        msgSender,
        block.timestamp
    );
}
```

## Recommendation

Revert the pump updates if they are called with zero reserve values.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An issue exists in the GeoEmaAndCumSmaPump component used by Beanstalk wells. The pump records a geometric exponential moving average (EMA) and a cumulative geometric simple moving average (SMA) for each token reserve. The implementation contains a comment that assumes every call to update() will be supplied with a non‑zero reserve value and that a zero reserve would set the geometric mean to zero. However, the Well contract does not enforce this assumption; it can legitimately call update() with a reserve of zero, for example after a remove‑liquidity‑one‑token operation that empties one side of the pool. When a zero reserve is passed, the pump silently writes zero into the EMA and SMA storage, causing the price oracle that reads these values to report a price of zero or otherwise distorted values. This distortion can be triggered by a normal user transaction and does not revert, making it exploitable by an attacker who can deliberately drive a reserve to zero and then rely on the corrupted oracle to manipulate downstream contracts that depend on the price feed. The impact includes incorrect price information, potential loss of funds for users who trade against a corrupted oracle, and increased MEV opportunities. The bug is discovered during a security audit by Cyfrin, where a test case demonstrated that after a series of swaps and a removal of liquidity, the second token reserve becomes zero and the subsequent pump update succeeds without reverting. The problem is hard to notice because a zero reserve may be a rare state and the contract does not emit an error; the only symptom is an unexpected zero or wildly inaccurate price. The correct mitigation is to add an explicit check in the pump’s update routine that reverts when any reserve argument is zero, thereby preventing the geometric mean from being set to zero and preserving the integrity of the oracle. In abstract terms, the vulnerability belongs to the class of invalid input handling leading to silent state corruption where a mathematical invariant (reserve > 0 for geometric mean) is violated without protection.
