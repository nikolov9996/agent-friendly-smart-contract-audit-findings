---
id: 25067
severity: "Medium"
---

# DeliHookConstantProduct swapping exactOutput and _feeFromOutput is incorrect

## Description



## Proof of Concept

Add the 2 following tests to SwapLifecycle_V2.t.sol:

```solidity
function testExactInputSwapZeroForOne() public {
    uint256 inputAmount = 5 ether;

    (uint128 r0Before, uint128 r1Before) = hook.getReserves(pid);
    uint256 bmxBefore = bmx.balanceOf(address(this));
    uint256 wbltBefore = wblt.balanceOf(address(this));

    // Perform exact input swap
    poolManager.unlock(abi.encode(address(bmx), inputAmount, true));

    (uint128 r0After, uint128 r1After) = hook.getReserves(pid);

    // Verify token balances
    assertEq(bmxBefore - bmx.balanceOf(address(this)), inputAmount, "BMX spent should match input");
    uint256 outputAmount = wblt.balanceOf(address(this)) - wbltBefore;

    assertEq(outputAmount, 4748297375815592703);
}

function testExactOutputZeroForOne() public {
    uint256 outputAmount = 4748297375815592703;

    (uint128 r0Before, uint128 r1Before) = hook.getReserves(pid);
    uint256 bmxBefore = bmx.balanceOf(address(this));
    uint256 wbltBefore = wblt.balanceOf(address(this));

    // Perform exact output swap
    poolManager.unlock(abi.encode(address(bmx), outputAmount, false));

    (uint128 r0After, uint128 r1After) = hook.getReserves(pid);

    // Verify output received
    assertEq(wblt.balanceOf(address(this)) - wbltBefore, outputAmount, "wBLT received should match output");
    uint256 inputAmount = bmxBefore - bmx.balanceOf(address(this));

    assertEq(inputAmount, 5000702855111981996); //@audit bigger than above of 5 ether
}
```

## Impact

User suffers a loss of 8.9%.

## Recommendation

Hinted at the solution in the root cause, to verify the fix, the fees have to match when swapping the same amounts.
