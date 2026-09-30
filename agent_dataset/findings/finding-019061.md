---
id: 19061
severity: "High"
---

# Incorrect solvency check because it multiplies collateralizationRate by share not amount when calculating liquidation threshold

## Description

```solidity
When a Collateralized Debt Position (CDP) reaches that liquidation threshold, it becomes eligible for liquidation and anyone can repay a position in exchange for a portion of the collateral. `Market._isSolvent` is used to check if the user is solvent. if not, then it can be liquidated. Here is the method body:
    
    function _isSolvent(
    	address user,
    	uint256 _exchangeRate
    ) internal view returns (bool) {
    	// accrue must have already been called!
    	uint256 borrowPart = userBorrowPart[user];
    	if (borrowPart == 0) return true;
    	uint256 collateralShare = userCollateralShare[user];
    	if (collateralShare == 0) return false;
    
    	Rebase memory _totalBorrow = totalBorrow;
    
    	return
    		yieldBox.toAmount(
    			collateralId,
    			collateralShare *
    				(EXCHANGE_RATE_PRECISION / FEE_PRECISION) *
    				collateralizationRate,
    			false
    		) >=
    		// Moved exchangeRate here instead of dividing the other side to preserve more precision
    		(borrowPart * _totalBorrow.elastic * _exchangeRate) /
    			_totalBorrow.base;
    }

[Code link](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/Market.sol#L402C1-L425C6)

The issue is that the collateralizationRate is multiplied by collateralShare (with precision constants) then converted to amount. This is incorrect, **the collateralizationRate sholud be used with amounts and not shares. Otherwise, we get wrong results**.
    
    yieldBox.toAmount(
    			collateralId,
    			collateralShare *
    				(EXCHANGE_RATE_PRECISION / FEE_PRECISION) *
    				collateralizationRate,
    			false
    		)

Please note that when using shares **it is not in favour of the protocol** , so amounts should be used instead. The only case where this is ok, is when the share/amount ratio is 1:1 which can not be, because totalAmount always get +1 and totalShares +1e8 to prevent 1:1 ratio type of attack.
    
        function _toAmount(
            uint256 share,
            uint256 totalShares_,
            uint256 totalAmount,
            bool roundUp
        ) internal pure returns (uint256 amount) {
            // To prevent reseting the ratio due to withdrawal of all shares, we start with
            // 1 amount/1e8 shares already burned. This also starts with a 1 : 1e8 ratio which
            // functions like 8 decimal fixed point math. This prevents ratio attacks or inaccuracy
            // due to 'gifting' or rebasing tokens. (Up to a certain degree)
            totalAmount++;
            totalShares_ += 1e8;

[Code link](https://github.com/Tapioca-DAO/YieldBox/blob/f5ad271b2dcab8b643b7cf622c2d6a128e109999/contracts/YieldBoxRebase.sol#L47-L52)

Moreover, in the method `_computeMaxAndMinLTVInAsset` which is supposed to returns the min and max LTV for user in asset price. Amount is used and not share. Here is the code:
    
    	function _computeMaxAndMinLTVInAsset(
    		uint256 collateralShare,
    		uint256 _exchangeRate
    	) internal view returns (uint256 min, uint256 max) {
    		uint256 collateralAmount = yieldBox.toAmount(
    			collateralId,
    			collateralShare,
    			false
    		);
    
    		max = (collateralAmount * EXCHANGE_RATE_PRECISION) / _exchangeRate;
    		min = (max * collateralizationRate) / FEE_PRECISION;
    	}

[Code Link](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/Market.sol#L428-L440)

I’ve set this to high severity because solvency check is a crucial part of the protocol. In short, we have :

  1. Inconsistency across the protocol
  2. Inaccuracy of calculating the liquidation threshold
  3. Not in favour of the protocol

Note: this is also applicable for ohter methods. For example, `Market._computeMaxBorrowableAmount`.
```

## Proof of Concept

```solidity
* When you run the PoC below, you will get the following results:

    [PASS] test_borrow_repay() (gas: 118001)
    Logs:
      ===BORROW===
      UserBorrowPart: 745372500000000000000
      Total Borrow Base: 745372500000000000000
      Total Borrow Elastic: 745372500000000000000
      ===356 days passed===
      Total Borrow Elastic: 749089151896269477984
      ===Solvency#1 => multiply by share===
      A: 749999999999925000000750007499999924999
      B: 749089151896269477984000000000000000000
      ===Solvency#2 => multiply by amount===
      A: 749999999999925000000750000000000000000
      B: 749089151896269477984000000000000000000
      ===Result===
      Solvency#1.A != Solvency#2.A
    
    Test result: ok. 1 passed; 0 failed; finished in 16.69ms

As you can see, numbers are not equal, and when using shares it is not in favour of the protocol, so amount should be used instead.

  * Code: Please note some lines in borrow method were commented out for simplicity. It is irrelevant anyway.
  * `_toAmount` copied from YieldBoxRebase

    // PoC => BIGBANG - Solvency Check Inaccuracy
    // Command => forge test -vv
    pragma solidity >=0.8.4 <0.9.0;
    
    import {Test} from "forge-std/Test.sol";
    import "forge-std/console.sol";
    
    import {DSTest} from "ds-test/test.sol";
    struct AccrueInfo {
        uint64 debtRate;
        uint64 lastAccrued;
    }
    
    struct Rebase {
        uint128 elastic;
        uint128 base;
    }
    
    /// @notice A rebasing library using overflow-/underflow-safe math.
    library RebaseLibrary {
        /// @notice Calculates the base value in relationship to `elastic` and `total`.
        function toBase(
            Rebase memory total,
            uint256 elastic,
            bool roundUp
        ) internal pure returns (uint256 base) {
            if (total.elastic == 0) {
                base = elastic;
            } else {
                base = (elastic * total.base) / total.elastic;
                if (roundUp && (base * total.elastic) / total.base < elastic) {
                    base++;
                }
            }
        }
    
        /// @notice Calculates the elastic value in relationship to `base` and `total`.
        function toElastic(
            Rebase memory total,
            uint256 base,
            bool roundUp
        ) internal pure returns (uint256 elastic) {
            if (total.base == 0) {
                elastic = base;
            } else {
                elastic = (base * total.elastic) / total.base;
                if (roundUp && (elastic * total.base) / total.elastic < base) {
                    elastic++;
                }
            }
        }
    
        /// @notice Add `elastic` to `total` and doubles `total.base`.
        /// @return (Rebase) The new total.
        /// @return base in relationship to `elastic`.
        function add(
            Rebase memory total,
            uint256 elastic,
            bool roundUp
        ) internal pure returns (Rebase memory, uint256 base) {
            base = toBase(total, elastic, roundUp);
            total.elastic += uint128(elastic);
            total.base += uint128(base);
            return (total, base);
        }
    
        /// @notice Sub `base` from `total` and update `total.elastic`.
        /// @return (Rebase) The new total.
        /// @return elastic in relationship to `base`.
        function sub(
            Rebase memory total,
            uint256 base,
            bool roundUp
        ) internal pure returns (Rebase memory, uint256 elastic) {
            elastic = toElastic(total, base, roundUp);
            total.elastic -= uint128(elastic);
            total.base -= uint128(base);
            return (total, elastic);
        }
    
        /// @notice Add `elastic` and `base` to `total`.
        function add(
            Rebase memory total,
            uint256 elastic,
            uint256 base
        ) internal pure returns (Rebase memory) {
            total.elastic += uint128(elastic);
            total.base += uint128(base);
            return total;
        }
    
        /// @notice Subtract `elastic` and `base` to `total`.
        function sub(
            Rebase memory total,
            uint256 elastic,
            uint256 base
        ) internal pure returns (Rebase memory) {
            total.elastic -= uint128(elastic);
            total.base -= uint128(base);
            return total;
        }
    
        /// @notice Add `elastic` to `total` and update storage.
        /// @return newElastic Returns updated `elastic`.
        function addElastic(
            Rebase storage total,
            uint256 elastic
        ) internal returns (uint256 newElastic) {
            newElastic = total.elastic += uint128(elastic);
        }
    
        /// @notice Subtract `elastic` from `total` and update storage.
        /// @return newElastic Returns updated `elastic`.
        function subElastic(
            Rebase storage total,
            uint256 elastic
        ) internal returns (uint256 newElastic) {
            newElastic = total.elastic -= uint128(elastic);
        }
    }
    
    contract BIGBANG_MOCK {
        using RebaseLibrary for Rebase;
        uint256 public collateralizationRate = 75000; // 75% // made public to access it from test contract
        uint256 public liquidationMultiplier = 12000; //12%
        uint256 public constant FEE_PRECISION = 1e5; // made public to access it from test contract
        uint256 public EXCHANGE_RATE_PRECISION = 1e18; //made public to access it from test contract
    
        uint256 public borrowOpeningFee = 50; //0.05%
        Rebase public totalBorrow;
        uint256 public totalBorrowCap;
        AccrueInfo public accrueInfo;
    
        /// @notice borrow amount per user
        mapping(address => uint256) public userBorrowPart;
    
        uint256 public USDO_balance; // just to track USDO balance of BigBang
    
        function _accrue() public {
            // made public so we can call it from the test contract
            AccrueInfo memory _accrueInfo = accrueInfo;
            // Number of seconds since accrue was called
            uint256 elapsedTime = block.timestamp - _accrueInfo.lastAccrued;
            if (elapsedTime == 0) {
                return;
            }
            //update debt rate // for simplicity we return bigBangEthDebtRate which is 5e15
            uint256 annumDebtRate = 5e15; // getDebtRate(); // 5e15 for eth. Check Penrose.sol Line:131
            _accrueInfo.debtRate = uint64(annumDebtRate / 31536000); //per second
    
            _accrueInfo.lastAccrued = uint64(block.timestamp);
    
            Rebase memory _totalBorrow = totalBorrow;
    
            uint256 extraAmount = 0;
    
            // Calculate fees
            extraAmount =
                (uint256(_totalBorrow.elastic) *
                    _accrueInfo.debtRate *
                    elapsedTime) /
                1e18;
            _totalBorrow.elastic += uint128(extraAmount);
    
            totalBorrow = _totalBorrow;
            accrueInfo = _accrueInfo;
    
            // emit LogAccrue(extraAmount, _accrueInfo.debtRate); // commented out since it irrelevant
        }
    
        function totalBorrowElastic() public view returns (uint128) {
            return totalBorrow.elastic;
        }
    
        function totalBorrowBase() public view returns (uint128) {
            return totalBorrow.base;
        }
    
        function _borrow(
            address from,
            address to,
            uint256 amount
        ) external returns (uint256 part, uint256 share) {
            uint256 feeAmount = (amount * borrowOpeningFee) / FEE_PRECISION; // A flat % fee is charged for any borrow
    
            (totalBorrow, part) = totalBorrow.add(amount + feeAmount, true);
            require(
                totalBorrowCap == 0 || totalBorrow.elastic <= totalBorrowCap,
                "BigBang: borrow cap reached"
            );
    
            userBorrowPart[from] += part; // toBase from RebaseLibrary. userBorrowPart stores the sharee
    
            //mint USDO
            // IUSDOBase(address(asset)).mint(address(this), amount); // not needed
            USDO_balance += amount;
    
            //deposit borrowed amount to user
            // asset.approve(address(yieldBox), amount);  // not needed
            // yieldBox.depositAsset(assetId, address(this), to, amount, 0); // not needed
            USDO_balance -= amount;
    
            // share = yieldBox.toShare(assetId, amount, false); // not needed
    
            // emit LogBorrow(from, to, amount, feeAmount, part); // not needed
        }
    
        // copied from YieldBoxRebase
        function _toAmount(
            uint256 share,
            uint256 totalShares_,
            uint256 totalAmount,
            bool roundUp
        ) external pure returns (uint256 amount) {
            // To prevent reseting the ratio due to withdrawal of all shares, we start with
            // 1 amount/1e8 shares already burned. This also starts with a 1 : 1e8 ratio which
            // functions like 8 decimal fixed point math. This prevents ratio attacks or inaccuracy
            // due to 'gifting' or rebasing tokens. (Up to a certain degree)
            totalAmount++;
            totalShares_ += 1e8;
    
            // Calculte the amount using te current amount to share ratio
            amount = (share * totalAmount) / totalShares_;
    
            // Default is to round down (Solidity), round up if required
            if (roundUp && (amount * totalShares_) / totalAmount < share) {
                amount++;
            }
        }
    }
    
    contract BIGBANG_ISSUES is DSTest, Test {
        BIGBANG_MOCK bigbangMock;
        address bob;
    
        function setUp() public {
            bigbangMock = new BIGBANG_MOCK();
            bob = vm.addr(1);
        }
    
        function test_borrow_repay() public {
            // borrow
            uint256 amount = 745e18;
    
            vm.warp(1 days);
            bigbangMock._accrue(); // acrrue before borrow (this is done on borrow)
    
            bigbangMock._borrow(bob, address(0), amount);
            console.log("===BORROW===");
            // console.log("Amount: %d", amount);
            console.log("UserBorrowPart: %d", bigbangMock.userBorrowPart(bob));
            console.log("Total Borrow Base: %d", bigbangMock.totalBorrowBase());
            console.log(
                "Total Borrow Elastic: %d",
                bigbangMock.totalBorrowElastic()
            );
    
            // time elapsed
            vm.warp(365 days);
            console.log("===356 days passed===");
            bigbangMock._accrue();
            console.log(
                "Total Borrow Elastic: %d",
                bigbangMock.totalBorrowElastic()
            ); 
    
            // Check Insolvency
    
            uint256 _exchangeRate = 1e18;
            uint256 collateralShare = 1000e18;
            uint256 totalShares = 1000e18;
            uint256 totalAmount = 1000e18;
            uint256 EXCHANGE_RATE_PRECISION = bigbangMock.EXCHANGE_RATE_PRECISION();
            uint256 FEE_PRECISION = bigbangMock.FEE_PRECISION();
            uint256 collateralizationRate = bigbangMock.collateralizationRate();
    
            uint256 borrowPart = bigbangMock.userBorrowPart(bob);
            uint256 _totalBorrowElastic = bigbangMock.totalBorrowElastic();
            uint256 _totalBorrowBase = bigbangMock.totalBorrowBase();
    
            console.log("===Solvency#1 => multiply by share===");
            // we pass totalShares and totalAmount
            uint256 A = bigbangMock._toAmount(
                collateralShare *
                    (EXCHANGE_RATE_PRECISION / FEE_PRECISION) *
                    collateralizationRate,
                totalShares,
                totalAmount,
                false
            );
    
            // Moved exchangeRate here instead of dividing the other side to preserve more precision
            uint256 B = (borrowPart * _totalBorrowElastic * _exchangeRate) /
                _totalBorrowBase;
    
            // bool isSolvent = A >= B;
    
            console.log("A: %d", A);
            console.log("B: %d", B);
    
            console.log("===Solvency#2 => multiply by amount===");
    
            A =
                bigbangMock._toAmount(
                    collateralShare,
                    totalShares,
                    totalAmount,
                    false
                ) *
                (EXCHANGE_RATE_PRECISION / FEE_PRECISION) *
                collateralizationRate;
    
            // Moved exchangeRate here instead of dividing the other side to preserve more precision
            B =
                (borrowPart * _totalBorrowElastic * _exchangeRate) /
                _totalBorrowBase;
    
            // isSolvent = A >= B;
    
            console.log("A: %d", A);
            console.log("B: %d", B);
    
            console.log("===Result===");
            console.log("Solvency#1.A != Solvency#2.A");
    
        }
    }
```

## Recommendation

```solidity
Use amount for calculation instead of shares. Check the PoC as it demonstrates such an example.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

An incorrect solvency check occurs in the market contract when determining whether a CDP can be liquidated. The check multiplies the user’s collateral share by the collateralizationRate (scaled by precision constants) before converting the share to an amount. Because the collateralizationRate is a ratio that should be applied to a monetary amount, applying it to a share distorts the computed collateral value. The conversion from share to amount uses a fixed‑point ratio that is deliberately offset (totalAmount++ and totalShares+=1e8) to prevent 1:1 attacks, so the share‑based calculation under‑estimates the true collateral value. As a result the contract may deem a position solvent when it is actually under‑collateralised, or vice‑versa, allowing a liquidator to trigger liquidation at an incorrect threshold. In practice a borrower whose collateral appears sufficient may be liquidated, losing part of their collateral, while the protocol may lose revenue because liquidations occur too early. The bug manifests whenever the _isSolvent function is called, which happens during liquidation eligibility checks, borrow, repay, or any operation that queries solvency. It affects all users of the market, the protocol’s liquidity pool, and any third‑party liquidators. The issue was discovered during a formal audit by Code4rena when the test suite compared the result of the share‑based calculation with an amount‑based calculation and observed a mismatch. The problem is subtle because the arithmetic uses large precision constants and the conversion function hides the share‑to‑amount ratio, making the error hard to spot by visual inspection. The vulnerability belongs to the class of incorrect financial ratio application or misuse of share versus amount in collateral valuation. An attacker can exploit it by opening a position that is close to the liquidation threshold, then waiting for the protocol to mis‑classify the position as solvent and force a liquidation at a favorable price, effectively stealing collateral. From a user’s perspective the UI may show a healthy collateralisation ratio while the transaction reverts with a solvency error or, conversely, a liquidation transaction may succeed unexpectedly, resulting in a loss of collateral. The fix is to perform the collateral valuation using the actual amount obtained from the share‑to‑amount conversion, and only then apply the collateralizationRate, ensuring that the same unit is used on both sides of the comparison. All other functions that compute liquidation thresholds, such as _computeMaxAndMinLTVInAsset and _computeMaxBorrowableAmount, should also be audited to guarantee they use amounts rather than shares.
