---
id: 18333
severity: "High"
---

# Risk of silent overflow in reserves update

## Description

The [`buy()`](https://github.com/code-423n4/2023-04-caviar/blob/main/src/PrivatePool.sol#L211) and [`sell()`](https://github.com/code-423n4/2023-04-caviar/blob/main/src/PrivatePool.sol#L301) functions update the `virtualBaseTokenReserves` and `virtualNftReserves` variables during each trade. However, these two variables are of type `uint128`, while the values that update them are of type `uint256`. This means that casting to a lower type is necessary, but this casting is performed without first checking that the values being cast can fit into the lower type. As a result, there is a risk of a silent overflow occurring during the casting process.

```solidity
function buy(uint256[] calldata tokenIds, uint256[] calldata tokenWeights, MerkleMultiProof calldata proof) 
    public
    payable
    returns (uint256 netInputAmount, uint256 feeAmount, uint256 protocolFeeAmount)
{
    // ~~~ Checks ~~~ //

    // calculate the sum of weights of the NFTs to buy
    uint256 weightSum = sumWeightsAndValidateProof(tokenIds, tokenWeights, proof);

    // calculate the required net input amount and fee amount
    (netInputAmount, feeAmount, protocolFeeAmount) = buyQuote(weightSum);
    ...
    // update the virtual reserves
    virtualBaseTokenReserves += uint128(netInputAmount - feeAmount - protocolFeeAmount); 
    virtualNftReserves -= uint128(weightSum);
    ...
```

If the reserves variables are updated with a silent overflow, it can lead to a breakdown of the xy=k equation. This, in turn, would result in a totally incorrect price calculation, causing potential financial losses for users or pool owners.

## Proof of Concept

Consider the scenario with a base token that has high decimals number described in the next test (add it to the `test/PrivatePool/Buy.t.sol`):

```solidity
function test_Overflow() public {
    // Setting up pool and base token HDT with high decimals number - 30
    // Initial balance of pool - 10 NFT and 100_000_000 HDT
    HighDecimalsToken baseToken = new HighDecimalsToken();
    privatePool = new PrivatePool(address(factory), address(royaltyRegistry), address(stolenNftOracle));
    privatePool.initialize(
        address(baseToken),
        nft,
        100_000_000 * 1e30,
        10 * 1e18,
        changeFee,
        feeRate,
        merkleRoot,
        true,
        false
    );

    // Minting NFT on pool address
    for (uint256 i = 100; i < 110; i++) {
        milady.mint(address(privatePool), i);
    }
    // Adding 8 NFT ids into the buying array
    for (uint256 i = 100; i < 108; i++) {
        tokenIds.push(i);
    }
    // Saving K constant (xy) value before the trade
    uint256 kBefore = uint256(privatePool.virtualBaseTokenReserves()) * uint256(privatePool.virtualNftReserves());

    // Minting enough HDT tokens and approving them for pool address
    (uint256 netInputAmount,, uint256 protocolFeeAmount) = privatePool.buyQuote(8 * 1e18);
    deal(address(baseToken), address(this), netInputAmount);
    baseToken.approve(address(privatePool), netInputAmount);

    privatePool.buy(tokenIds, tokenWeights, proofs);

    // Saving K constant (xy) value after the trade
    uint256 kAfter = uint256(privatePool.virtualBaseTokenReserves()) * uint256(privatePool.virtualNftReserves());

    // Checking that K constant succesfully was changed due to silent overflow
    assertEq(kBefore, kAfter, "K constant was changed");
}
```

Also add this contract into the end of `Buy.t.sol` file for proper test work:

```solidity
contract HighDecimalsToken is ERC20 {
    constructor() ERC20("High Decimals Token", "HDT", 30) {}
}
```

## Recommendation

Add checks that the casting value is not greater than the `uint128` type max value:

    File: PrivatePool.sol
    229:         // update the virtual reserves
    +            if (netInputAmount - feeAmount - protocolFeeAmount > type(uint128).max) revert Overflow();
    230:         virtualBaseTokenReserves += uint128(netInputAmount - feeAmount - protocolFeeAmount); 
    +            if (weightSum > type(uint128).max) revert Overflow();
    231:         virtualNftReserves -= uint128(weightSum);

    File: PrivatePool.sol
    322:         // update the virtual reserves
    +            if (netOutputAmount + protocolFeeAmount + feeAmount > type(uint128).max) revert Overflow();
    323:         virtualBaseTokenReserves -= uint128(netOutputAmount + protocolFeeAmount + feeAmount);
    +            if (weightSum > type(uint128).max) revert Overflow();
    324:         virtualNftReserves += uint128(weightSum);

The Warden has identified a risky underflow due to unsafe casting, the underflow would cause the invariants of the protocol to be broken, causing it to behave in undefined ways, most likely allowing to discount tokens (principal)

I have considered downgrading to Medium Severity

However, I believe that in multiple cases the subtractions `netInputAmount - feeAmount - protocolFeeAmount` which could start with `netInputAmount > type(uint128).max` would not necessarily fall within a `uint128`

For this reason, I believe the finding to be of High Severity.

Fixed in <https://github.com/outdoteth/caviar-private-pools/pull/10>.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An overflow vulnerability exists in the pool contract when updating virtual reserves. The contract stores virtualBaseTokenReserves and virtualNftReserves as uint128, but the calculations that modify them use uint256 values (net input amount minus fees, weight sum, etc.). The code casts the uint256 result directly to uint128 without checking that the value fits. If the computed amount exceeds 2^128‑1, the cast silently truncates the high bits, causing the stored reserve to wrap around to a much smaller number. This break the invariant xy = k that underpins the constant‑product pricing formula. As a result the pool can report an incorrect price, allowing trades at far‑from‑market rates and potentially draining user funds. The overflow can happen during a buy or sell transaction when the base token has a very large decimal precision or when a large amount of tokens is transferred, as demonstrated by a test that uses a 30‑decimal ERC20 token and a pool initialized with 100 000 000 * 1e30 base tokens. From a user’s perspective the trade appears to succeed, but the pool’s internal accounting is corrupted: subsequent swaps may return zero or excessive amounts, balances may disappear, and the expected K constant changes unexpectedly. The issue was discovered during a formal audit by Code4rena, where the auditors observed the unchecked cast and reproduced the overflow with a high‑precision token. The bug is subtle because the transaction does not revert and no event signals the overflow, making it hard to notice without inspecting the reserve values after the trade. The proper fix is to add explicit checks that the value to be cast does not exceed type(uint128).max before performing the cast, and to revert with an overflow error if it does. This restores the safety of the reserve updates and preserves the constant‑product invariant.
