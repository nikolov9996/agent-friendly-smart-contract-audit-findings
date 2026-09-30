---
id: 1844
severity: "Medium"
---

# The MixOracle.getThePrice function calculates the price incorrectly using the TarotOracle.getResult function as the TWAP price Found by KupiaSec

## Description

The MixOracle.getThePrice function calculates the price using the TarotOracle contract and the pyth oracle. However, it incorrectly uses the TarotOracle.getResult function as the TWAP price, which disrupts the matching mechanism for lend and borrow orders. In the MixOracle.getThePrice function, the twapPrice112x112 is retrieved from the TarotOracle.getResult function at L50. It then calculates the price of 1 token1 in USD using twapPrice112x112 and the price from the pyth oracle at L65.

```solidity
ITarotOracle priceFeed = ITarotOracle(_priceFeed);
address uniswapPair = AttachedUniswapPair[tokenAddress];
require(isFeedAvailable[uniswapPair], "Price feed not available");
(uint224 twapPrice112x112, ) = priceFeed.getResult(uniswapPair);
[...]
int amountOfAttached = int(
    (((2 ** 112)) * (10 ** decimalsToken1)) / twapPrice112x112
);
uint price = (uint(amountOfAttached) * uint(attachedTokenPrice)) /
    (10 ** decimalsToken1);
```

The TarotOracle.getResult function returns the time-weighted average of reserve0 + price, rather than the TWAP price, from L46. Also, it does not synchronize with uniswapV2Pair.

File: contracts\oracles\MixOracle\TarotOracle\TarotPriceOracle.sol
```solidity
function getPriceCumulativeCurrent(
    address uniswapV2Pair
) internal view returns (uint256 priceCumulative) {
    priceCumulative = IUniswapV2Pair(uniswapV2Pair)
        .reserve0CumulativeLast();
    (
        uint112 reserve0,
        uint112 reserve1,
        uint32 _blockTimestampLast
    ) = IUniswapV2Pair(uniswapV2Pair).getReserves();
    uint224 priceLatest = UQ112x112.encode(reserve1).uqdiv(reserve0);
    uint32 timeElapsed = getBlockTimestamp() - _blockTimestampLast; // overflow is desired
    // * never overflows, and + overflow is desired
    priceCumulative += (uint256(priceLatest) * timeElapsed);
}
```

This means that the twapPrice112x112 in the MixOracle.getThePrice function is not the correct TWAP price. Consequently, the DebitaV3Aggregator.matchOffersV3 uses an incorrect price to match lend and borrow orders.

Internal pre-conditions  
A user creates the order with MixOracle.

External pre-conditions  
1. None

Attack Path  
None

The incorrect price from the MixOracle disrupts the matching mechanism for lend and borrow orders. This causes user's loss of funds.

## Proof of Concept

Change the code in the MixOracle.getThePrice function to get the correct price from the uniswapV2Pair.

File: code\Debita-V3-Contracts\contracts\oracles\MixOracle\MixOracle.sol
```solidity
- function getThePrice(address tokenAddress) public returns (int) {
+ function getTotalPrice(address tokenAddress, address uniswapV2Pair) public returns (int, int) {
    // get tarotOracle address
    address _priceFeed = AttachedTarotOracle[tokenAddress];
    require(_priceFeed != address(0), "Price feed not set");
    require(!isPaused, "Contract is paused");
    ITarotOracle priceFeed = ITarotOracle(_priceFeed);
    address uniswapPair = AttachedUniswapPair[tokenAddress];
    require(isFeedAvailable[uniswapPair], "Price feed not available");
    // get twap price from token1 in token0
    (uint224 twapPrice112x112, ) = priceFeed.getResult(uniswapPair);
    address attached = AttachedPricedToken[tokenAddress];
    // Get the price from the pyth contract, no older than 20 minutes
    // get usd price of token0
    int attachedTokenPrice = IPyth(debitaPythOracle).getThePrice(attached);
    uint decimalsToken1 = ERC20(attached).decimals();
    uint decimalsToken0 = ERC20(tokenAddress).decimals();
    // calculate the amount of attached token that is needed to get 1 token1
    int amountOfAttached = int(
        (((2 ** 112)) * (10 ** decimalsToken1)) / twapPrice112x112
    );
    // calculate the price of 1 token1 in usd based on the attached token
    uint price = (uint(amountOfAttached) * uint(attachedTokenPrice)) /
        (10 ** decimalsToken1);
    require(price > 0, "Invalid price");
-   return int(uint(price));
    uint wftmPrice = IUniswapV2Pair(uniswapV2Pair).current(tokenAddress, 1e18);
    // uint realPrice = (uint(attachedTokenPrice)) * wftmPrice;
    uint realPrice = (uint(attachedTokenPrice)) * wftmPrice / (10 ** decimalsToken1);
    return (int(uint(price)), int(uint(realPrice)));
}
```

And add the following testTotalPrice test function in the OracleTarotUSDCEQUAL.t.sol.

File: code\Debita-V3-Contracts\test\fork\Loan\ltv\Tarot-Fantom\OracleTarotUSDCEQUAL.t.sol
```solidity
function testTotalPrice() public {
    IUniswapV2Pair(EQUALPAIR).sync();
    DebitaMixOracle.setAttachedTarotPriceOracle(EQUALPAIR);
    vm.warp(block.timestamp + 1201);
    IUniswapV2Pair(EQUALPAIR).sync();
    (int originPrice, int realPrice) = DebitaMixOracle.getTotalPrice(EQUAL, EQUALPAIR);

    console.logString(" price:");
    console.logUint(uint(originPrice));
    console.logString("actual price:");
    console.logUint(uint(realPrice));
    console.logString("price diff ratio:");
    console.logUint(uint(originPrice / realPrice));
}
```

Use the following command to test above function.
forge test --rpc-url https://mainnet.base.org --match-path test/fork/Loan/ltv/Tarot-Fantom/OracleTarotUSDCEQUAL.t.sol --match-test testTotalPrice -vvv

The result is as following:
mix price:
147639521176897807
actual price:
926069876
price diff ratio:
159425897

This indicates that the mix price is 147,639,521,176,897,807, while the actual price is 926,069,876. The mix price is significantly higher than the actual price.

## Recommendation

It is recommended to change the code as following:

File: code\Debita-V3-Contracts\contracts\oracles\MixOracle\MixOracle.sol
```solidity
function getThePrice(address tokenAddress) public returns (int) {
    address _priceFeed = AttachedTarotOracle[tokenAddress];
    require(_priceFeed != address(0), "Price feed not set");
    require(!isPaused, "Contract is paused");
    ITarotOracle priceFeed = ITarotOracle(_priceFeed);
    address uniswapPair = AttachedUniswapPair[tokenAddress];
    require(isFeedAvailable[uniswapPair], "Price feed not available");
    (uint224 twapPrice112x112, ) = priceFeed.getResult(uniswapPair);
    //+
    uint224 twapPrice112x112 =
        uint224(IUniswapV2Pair(uniswapV2Pair).current(tokenAddress, 1e18));
    address attached = AttachedPricedToken[tokenAddress];
    // Get the price from the pyth contract, no older than 20 minutes
    // get usd price of token0
    int attachedTokenPrice = IPyth(debitaPythOracle).getThePrice(attached);
    uint decimalsToken1 = ERC20(attached).decimals();
    uint decimalsToken0 = ERC20(tokenAddress).decimals();
    // calculate the amount of attached token that is needed to get 1 token1
    int amountOfAttached = int(
        (((2 ** 112)) * (10 ** decimalsToken1)) / twapPrice112x112
    );
    // calculate the price of 1 token1 in usd based on the attached token
    uint price = (uint(amountOfAttached) * uint(attachedTokenPrice)) /
        (10 ** decimalsToken1);
    require(price > 0, "Invalid price");
    return int(uint(price));
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the MixOracle.getThePrice function, which is intended to provide a time‑weighted average price (TWAP) for a token by combining data from a TarotOracle contract and a Pyth price feed. Instead of using a true TWAP, the function calls TarotOracle.getResult and treats the returned value, named twapPrice112x112, as if it were the TWAP price. In reality, TarotOracle.getResult returns the cumulative sum of reserve0 plus price, derived from the UniswapV2 pair’s reserve0CumulativeLast and a price‑latest calculation, without synchronising with the pair’s current state. Consequently, the value used by MixOracle is not a proper TWAP but an inflated cumulative figure. This mis‑calculation propagates to the DebitaV3Aggregator.matchOffersV3 routine, which relies on the price supplied by MixOracle to match lend and borrow orders. Because the price is dramatically higher than the true market price, orders are matched at incorrect rates, causing borrowers to receive less value than expected and lenders to be under‑compensated. From a user’s perspective the symptoms are a mismatch between the expected loan terms and the actual execution: a user may see a loan being liquidated immediately, balances dropping to zero, or refunds that should be received being missing. The issue occurs whenever MixOracle is used to fetch a price for any token that has an attached TarotOracle feed, i.e., under normal protocol operation. The affected parties include all lenders, borrowers, and the protocol itself, as the accounting logic that assumes a correct TWAP is broken. The flaw was discovered during a security audit performed by KupiaSec, which identified that the oracle call does not return a TWAP and that the contract does not synchronise with the Uniswap pair. The problem is subtle because the returned number is still a uint112 and does not trigger a revert, making the price appear plausible while being orders of magnitude off. The vulnerability belongs to the class of oracle mis‑use bugs, specifically the use of an incorrect price source for TWAP calculations, leading to accounting errors and potential fund loss. To remediate the issue the contract should replace the call to TarotOracle.getResult with a direct query of the UniswapV2 pair’s current price (for example using a function that returns the instantaneous price or a correctly computed TWAP) and ensure the pair is synchronised before the price is read. The fix restores the intended invariant that the price used for matching reflects the true market TWAP, thereby aligning protocol economics with user expectations and preventing inadvertent loss of funds.
