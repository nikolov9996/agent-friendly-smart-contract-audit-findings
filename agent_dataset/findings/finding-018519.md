---
id: 18519
severity: "High"
---

# Position NFT can be spammed with insignificant positions by anyone until rewards DoS

## Description

```solidity
The [PositionManager.memorializePositions(params_)](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L170-L216) method can be called by **anyone** (per design, see 3rd party test cases) and allows **insignificantly** small (any value > 0) positions to be attached to **anyone** else’s positions NFT, see PoC. As a result, the `positionIndexes[params_.tokenId]` storage array for an NFT with given token ID can be spammed with positions without the NFT owner’s consent.

Therefore, the [PositionManager.getPositionIndexesFiltered(tokenId_)](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L466-L485) method might exceed the block gas limit when iterating the `positionIndexes[tokenId_]` storage array. However, the [RewardsManager.calculateRewards(…)](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/RewardsManager.sol#L325-L349) and [RewardsManager._calculateAndClaimRewards(…)](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/RewardsManager.sol#L384-L414) methods rely on the aforementioned method to succeed in order to calculate and pay rewards.

All in all, a griefer can spam anyone’s position NFT with insignificant positions until the rewards mechanism fails for the NFT owner due to DoS (gas limit). Side note: A position NFT also cannot be burned as long as such insignificant positions are attached to it, see [PositionManager.burn(…)](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L142-L154).
```

## Proof of Concept

```diff
The following _diff_ is based on the existing test case `testMemorializePositions` in `PositionManager.t.sol` and demonstrates that insignificant positions can be attached by anyone.
    
    diff --git a/ajna-core/tests/forge/unit/PositionManager.t.sol b/ajna-core/tests/forge/unit/PositionManager.t.sol
    index bf3aa40..56c85d1 100644
    --- a/ajna-core/tests/forge/unit/PositionManager.t.sol
    +++ b/ajna-core/tests/forge/unit/PositionManager.t.sol
    @@ -122,6 +122,7 @@ contract PositionManagerERC20PoolTest is PositionManagerERC20PoolHelperContract
          */
         function testMemorializePositions() external {
             address testAddress = makeAddr("testAddress");
             address otherAddress = makeAddr("otherAddress");
             uint256 mintAmount  = 10000 * 1e18;
    
             _mintQuoteAndApproveManagerTokens(testAddress, mintAmount);
    @@ -134,17 +135,17 @@ contract PositionManagerERC20PoolTest is PositionManagerERC20PoolHelperContract
    
             _addInitialLiquidity({
                 from:   testAddress,
                 amount: 1, //3_000 * 1e18,
                 index:  indexes[0]
             });
             _addInitialLiquidity({
                 from:   testAddress,
                 amount: 1, //3_000 * 1e18,
                 index:  indexes[1]
             });
             _addInitialLiquidity({
                 from:   testAddress,
                 amount: 1, // 3_000 * 1e18,
                 index:  indexes[2]
             });
    
    @@ -165,17 +166,20 @@ contract PositionManagerERC20PoolTest is PositionManagerERC20PoolHelperContract
    
             // allow position manager to take ownership of the position
             uint256[] memory amounts = new uint256[](3);
             amounts[0] = 1; //3_000 * 1e18;
             amounts[1] = 1; //3_000 * 1e18;
             amounts[2] = 1; //3_000 * 1e18;
             _pool.increaseLPAllowance(address(_positionManager), indexes, amounts);
    
             // memorialize quote tokens into minted NFT
             changePrank(otherAddress); // switch other address (not owner of NFT)
             vm.expectEmit(true, true, true, true);
             emit TransferLP(testAddress, address(_positionManager), indexes, 3 /*9_000 * 1e18*/);
             vm.expectEmit(true, true, true, true);
             emit MemorializePosition(testAddress, tokenId, indexes);
             _positionManager.memorializePositions(memorializeParams);  // switch back to test address (owner of NFT)
             changePrank(testAddress);
    
             // check memorialization success
             uint256 positionAtPriceOneLP = _positionManager.getLP(tokenId, indexes[0]);
```

## Recommendation

```solidity
Requiring that The [PositionManager.memorializePositions(params_)](https://github.com/code-423n4/2023-05-ajna/blob/276942bc2f97488d07b887c8edceaaab7a5c3964/ajna-core/src/PositionManager.sol#L170-L216) can only be called by the NFT owner or anyone who has approval would help but break the 3rd party test cases.

Alternatively, one could enforce a minimum position value to make this griefing attack extremely unattractive.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service (DoS) vector that stems from the public accessibility of the PositionManager.memorializePositions function. Because the function does not restrict the caller to the NFT owner or an approved operator, any external address can invoke it with a tokenId that belongs to another user and attach a position of arbitrarily small size (any amount greater than zero). The contract stores each attached position in the positionIndexes array that is linked to the NFT’s tokenId. Since there is no minimum‑value check, an attacker can repeatedly call the function, flooding the array with a large number of insignificant entries. When the RewardsManager later calls PositionManager.getPositionIndexesFiltered to iterate over that array in order to calculate rewards, the iteration may exceed the block gas limit, causing the rewards calculation transaction to run out of gas and revert. Consequently, the NFT owner is unable to claim accrued rewards, sees a zero‑reward balance in the UI, and may also be prevented from burning the NFT because the burn function checks that the positionIndexes array is empty. The issue occurs whenever the contract is deployed with the current access‑control design and when an adversary is motivated to spam positions; it is not dependent on any specific token value or market condition. The affected parties are the owners of position NFTs, the protocol’s reward distribution mechanism, and any users who rely on the ability to burn their NFTs after use. The problem was discovered during a formal audit when a test case demonstrated that a non‑owner could successfully call memorializePositions with a minimal amount and that the resulting array growth could cause gas‑limit failures. The bug is subtle because the added positions appear legitimate—each entry satisfies the >0 check—so the contract does not revert or emit an obvious error, making the attack hard to detect from transaction logs alone. Conceptually, the flaw belongs to the class of unbounded‑array‑growth and missing access‑control vulnerabilities that enable griefing attacks. To remediate, the contract should either restrict memorializePositions to the NFT owner or an approved operator, or enforce a sensible minimum position size that makes spamming economically infeasible. Either mitigation would prevent arbitrary users from inflating the positionIndexes array and restore reliable reward calculation and NFT burnability.
