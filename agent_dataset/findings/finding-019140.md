---
id: 19140
severity: "High"
---

# Bond operations will always revert at certain time when `putOptionsRequired` is true

## Description

when `putOptionsRequired` is `true`, there is period of time where bond operations will always revert when try to purchase options from perp atlantic vault.

## Proof of Concept

When `bond` is called and `putOptionsRequired` is `true`, it will call `_purchaseOptions` providing the calculated `rdpxRequired`.

```solidity
function bond(
  uint256 _amount,
  uint256 rdpxBondId,
  address _to
) public returns (uint256 receiptTokenAmount) {
  _whenNotPaused();
  // Validate amount
  _validate(_amount > 0, 4);

  // Compute the bond cost
  (uint256 rdpxRequired, uint256 wethRequired) = calculateBondCost(
    _amount,
    rdpxBondId
  );

  IERC20WithBurn(weth).safeTransferFrom(
    msg.sender,
    address(this),
    wethRequired
  );

  // update weth reserve
  reserveAsset[reservesIndex["WETH"]].tokenBalance += wethRequired;

  // purchase options
  uint256 premium;
  if (putOptionsRequired) {
    premium = _purchaseOptions(rdpxRequired);
  }

  _transfer(rdpxRequired, wethRequired - premium, _amount, rdpxBondId);

  // Stake the ETH in the ReceiptToken contract
  receiptTokenAmount = _stake(_to, _amount);

  // reLP
  if (isReLPActive) IReLP(addresses.reLPContract).reLP(_amount);

  emit LogBond(rdpxRequired, wethRequired, receiptTokenAmount);
}
```

Inside `_purchaseOptions`, it will call `PerpetualAtlanticVault.purchase` providing the amount and `address(this)` as receiver :

```solidity
function _purchaseOptions(
  uint256 _amount
) internal returns (uint256 premium) {
  /**
   * Purchase options and store ERC721 option id
   * Note that the amount of options purchased is the amount of rDPX received
   * from the user to sufficiently collateralize the underlying DpxEth stored in the bond
   **/
  uint256 optionId;

  (premium, optionId) = IPerpetualAtlanticVault(
    addresses.perpetualAtlanticVault
  ).purchase(_amount, address(this));

  optionsOwned[optionId] = true;
  reserveAsset[reservesIndex["WETH"]].tokenBalance -= premium;
}
```

Then inside `purchase`, it will calculate `premium` using `calculatePremium` function, providing `strike`, `amount`, `timeToExpiry`.

```solidity
function purchase(
  uint256 amount,
  address to
)
  external
  nonReentrant
  onlyRole(RDPXV2CORE_ROLE)
  returns (uint256 premium, uint256 tokenId)
{
  _whenNotPaused();
  _validate(amount > 0, 2);

  updateFunding();

  uint256 currentPrice = getUnderlyingPrice(); // price of underlying wrt collateralToken
  uint256 strike = roundUp(currentPrice - (currentPrice / 4)); // 25% below the current price
  IPerpetualAtlanticVaultLP perpetualAtlanticVaultLp = IPerpetualAtlanticVaultLP(
      addresses.perpetualAtlanticVaultLP
    );

  // Check if vault has enough collateral to write the options
  uint256 requiredCollateral = (amount * strike) / 1e8;

  _validate(
    requiredCollateral <= perpetualAtlanticVaultLp.totalAvailableCollateral(),
    3
  );

  uint256 timeToExpiry = nextFundingPaymentTimestamp() - block.timestamp;

  // Get total premium for all options being purchased
  premium = calculatePremium(strike, amount, timeToExpiry, 0);

  // ... rest of operations
}
```

Inside this `calculatePremium`, it will get price from option pricing :

```solidity
function calculatePremium(
  uint256 _strike,
  uint256 _amount,
  uint256 timeToExpiry,
  uint256 _price
) public view returns (uint256 premium) {
  premium = ((IOptionPricing(addresses.optionPricing).getOptionPrice(
    _strike,
    _price > 0 ? _price : getUnderlyingPrice(),
    getVolatility(_strike),
    timeToExpiry
  ) * _amount) / 1e8);
}
```

The provided `OptionPricingSimple.getOptionPrice` will use Black-Scholes model to calculate the price :

```solidity
function calculate(
  uint8 optionType,
  uint256 price,
  uint256 strike,
  uint256 timeToExpiry,
  uint256 riskFreeRate,
  uint256 volatility
) internal pure returns (uint256) {
  bytes16 S = ABDKMathQuad.fromUInt(price);
  bytes16 X = ABDKMathQuad.fromUInt(strike);
  bytes16 T = ABDKMathQuad.div(
    ABDKMathQuad.fromUInt(timeToExpiry),
    ABDKMathQuad.fromUInt(36500) // 365 * 10 ^ DAYS_PRECISION
  );
  bytes16 r = ABDKMathQuad.div(
    ABDKMathQuad.fromUInt(riskFreeRate),
    ABDKMathQuad.fromUInt(10000)
  );
  bytes16 v = ABDKMathQuad.div(
    ABDKMathQuad.fromUInt(volatility),
    ABDKMathQuad.fromUInt(100)
  );
  bytes16 d1 = ABDKMathQuad.div(
    ABDKMathQuad.add(
      ABDKMathQuad.ln(ABDKMathQuad.div(S, X)),
      ABDKMathQuad.mul(
        ABDKMathQuad.add(
          r,
          ABDKMathQuad.mul(v, ABDKMathQuad.div(v, ABDKMathQuad.fromUInt(2)))
        ),
        T
      )
    ),
    ABDKMathQuad.mul(v, ABDKMathQuad.sqrt(T))
  );
  bytes16 d2 = ABDKMathQuad.sub(
    d1,
    ABDKMathQuad.mul(v, ABDKMathQuad.sqrt(T))
  );
  if (optionType == OPTION_TYPE_CALL) {
    return
      ABDKMathQuad.toUInt(
        ABDKMathQuad.mul(
          _calculateCallTimeDecay(S, d1, X, r, T, d2),
          ABDKMathQuad.fromUInt(DIVISOR)
        )
      );
  } else if (optionType == OPTION_TYPE_PUT) {
    return
      ABDKMathQuad.toUInt(
        ABDKMathQuad.mul(
          _calculatePutTimeDecay(X, r, T, d2, S, d1),
          ABDKMathQuad.fromUInt(DIVISOR)
        )
      );
  } else return 0;
}
```

The problem lies inside `calculatePremium` due to not properly check if current time less than 864 seconds (around 14 minutes). because `getOptionPrice` will use time expiry in days multiply by 100.

```solidity
uint256 timeToExpiry = (expiry * 100) / 86400;
```

If `nextFundingPaymentTimestamp() - block.timestamp` is less than 864 seconds, it will cause `timeToExpiry` inside option pricing is 0 and the call will always revert. This will cause an unexpected revert period around 14 minutes every funding epoch (in this case every week).

Foundry PoC :

Try to simulate `calculatePremium` when `nextFundingPaymentTimestamp() - block.timestamp` is less than 864 seconds.

Add this test to `Unit` contract inside `/tests/rdpxV2-core/Unit.t.sol`, also add `import "forge-std/console.sol";` and `import {OptionPricingSimple} from "contracts/libraries/OptionPricingSimple.sol";` in the contract :
    
```solidity
function testOptionPricingRevert() public {
  OptionPricingSimple optionPricingSimple;
  optionPricingSimple = new OptionPricingSimple(100, 5e6);

  (uint256 rdpxRequired, uint256 wethRequired) = rdpxV2Core
      .calculateBondCost(1 * 1e18, 0);

  uint256 currentPrice = vault.getUnderlyingPrice(); // price of underlying wrt collateralToken
  uint256 strike = vault.roundUp(currentPrice - (currentPrice / 4)); // 25% below the current price
  // around 14 minutes before next funding payment
  vm.warp(block.timestamp + 7 days - 863 seconds);
  uint256 timeToExpiry = vault.nextFundingPaymentTimestamp() -
      block.timestamp;
  console.log("What is the current price");
  console.log(currentPrice);
  console.log("What is the strike");
  console.log(strike);
  console.log("What is time to expiry");
  console.log(timeToExpiry);
  uint256 price = vault.getUnderlyingPrice();
  // will revert
  vm.expectRevert();
  optionPricingSimple.getOptionPrice(strike, price, 100, timeToExpiry);
}
```

## Recommendation

Set minimum `timeToExpiry` inside `calculatePremium` :
    
```solidity
function calculatePremium(
  uint256 _strike,
  uint256 _amount,
  uint256 timeToExpiry,
  uint256 _price
) public view returns (uint256 premium) {
  premium = ((IOptionPricing(addresses.optionPricing).getOptionPrice(
    _strike,
    _price > 0 ? _price : getUnderlyingPrice(),
    getVolatility(_strike),
    timeToExpiry < 864 ? 864 : timeToExpiry
  ) * _amount) / 1e8);
}
```

Modify time to expiry with a check for less than 864 seconds and make it more robust.

The DOS is not conditional on an external requirement because it consistently happens, I’ll ask judges, but am maintaining High Severity at this time.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a deterministic denial‑of‑service condition that occurs when the contract’s putOptionsRequired flag is true and a bond operation attempts to purchase put options from the PerpetualAtlanticVault during a short window before the next funding payment. The root cause is that the calculatePremium function forwards the raw timeToExpiry value (nextFundingPaymentTimestamp() ‑ block.timestamp) to the option pricing library without enforcing a minimum duration. The pricing library expects the time to expiry expressed in days multiplied by a precision factor; when the raw value is less than 864 seconds (approximately fourteen minutes) the conversion yields a zero timeToExpiry, which triggers a revert inside OptionPricingSimple.getOptionPrice. An attacker does not need to supply malicious input – the revert is triggered purely by blockchain time, making the bug easy to hit for any user who initiates a bond in that interval. Exploitation consists of a user calling bond while putOptionsRequired is true; the internal call to _purchaseOptions invokes PerpetualAtlanticVault.purchase, which calculates premium with the too‑small timeToExpiry, causing the transaction to revert. The impact is that legitimate users cannot complete bond transactions for roughly fourteen minutes each funding epoch (weekly in the current deployment), resulting in lost opportunity to acquire rDPX, no receipt tokens are minted, and the protocol’s liquidity provisioning is temporarily halted. The condition affects any participant trying to bond when the flag is active; funds are never transferred because the whole transaction reverts, but the user experience is a sudden failure with no receipt token and a generic revert message. The issue was discovered during a formal audit by reproducing the edge case in a Foundry unit test that warped the block timestamp to just before the funding deadline and observed the expected revert. It is hard to notice in normal testing because the problematic time window is narrow and only appears at a specific point in the funding cycle. To remediate, the calculatePremium function should enforce a lower bound on timeToExpiry (e.g., clamp values below 864 seconds to 864) before passing it to the pricing library, ensuring the pricing formula always receives a non‑zero expiry and preventing the revert. This class of bug is a time‑dependent input validation error that leads to a denial‑of‑service by violating the business assumption that options can always be priced, breaking the accounting flow that expects a premium to be deducted from the WETH reserve.
