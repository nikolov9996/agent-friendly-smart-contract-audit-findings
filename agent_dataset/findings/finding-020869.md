---
id: 20869
severity: "High"
---

# Attacker can amplify a rounding error in MagicLP to break the I invariant and cause malicious pricing

## Description

One of the two key parameters in MagicLP pools is `I`, which is defined to be the ideal ratio between the two reserves. It is set during MagicLP initialization: `_I_ = i;`

It is used when performing the initial LP deposit, in `buyShares()`:
```solidity
    if (totalSupply() == 0) {
        // case 1. initial supply
        if (quoteBalance == 0) {
            revert ErrZeroQuoteAmount();
        }
        shares = quoteBalance < DecimalMath.mulFloor(baseBalance, _I_) ? DecimalMath.divFloor(quoteBalance, _I_) : baseBalance;
        _BASE_TARGET_ = shares.toUint112();
        _QUOTE_TARGET_ = DecimalMath.mulFloor(shares, _I_).toUint112();
        if (_QUOTE_TARGET_ == 0) {
            revert ErrZeroQuoteTarget();
        }
        if (shares <= 2001) {
            revert ErrMintAmountNotEnough();
        }
        _mint(address(0), 1001);
        shares -= 1001;
```
The `QUOTE_TARGET` is determined by multiplying the `BASE_TARGET` with `I`.

The flaw is in the check below: `shares = quoteBalance < DecimalMath.mulFloor(baseBalance, _I_) ? DecimalMath.divFloor(quoteBalance, _I_) : baseBalance;` Essentially there needs to be enough `quoteBalance` at the `I` ratio to mint `baseBalance` shares, if there’s not enough then shares are instead determined by dividing the `quoteBalance` with `I`. An attacker can abuse the `mulFloor()` to create a major inconsistency. Suppose `quoteBalance = 1`, `baseBalance = 19999`, `I = 1e14`. Then we have: `1 < 19999 * 1e14 / 1e18 => 1 < 1 => False` Therefore `shares = 19999` . It sets the targets:
    
    _BASE_TARGET_ = 19999
    _QUOTE_TARGET_ = 19999 * 1e14 / 1e18 = 1

The result is the ratio 1:19999, when the intended ratio from `I` is 1:1000.

Essentially a small rounding error is magnified. The rounding direction should instead be: `quoteBalance < DecimalMath.mulCeil(baseBalance, _I_)` This would ensure that `DecimalMath.divFloor(quoteBalance, _I_)` is executed. At this point, when calculating `QUOTE_TARGET` there will not be a precision error as above (it performs the opposing actions to the divFloor).

An attacker can abuse it by making users perform trades under the assumption `I` is the effective ratio, however the ratio is actually `2I`. The pool’s pricing mechanics will be wrong. Note that users will legitimately trust any MagicLP pool created by the Factory as it is supposed to enforce that ratio.

The attack can be performed on another entity’s pool right after the `init()` call, or on a self-created pool. The initial cost for the attack is very small due to the small numbers involved.

## Proof of Concept

Step by step of the initial `buyShares()` was provided above. `_QUOTE_TARGET_` is used by the pricer:
```solidity
    function getPMMState() public view returns (PMMPricing.PMMState memory state) {
        state.i = _I_;
        state.K = _K_;
        state.B = _BASE_RESERVE_;
        state.Q = _QUOTE_RESERVE_;
        state.B0 = _BASE_TARGET_; // will be calculated in adjustedTarget
        state.Q0 = _QUOTE_TARGET_;
        state.R = PMMPricing.RState(_RState_);
        PMMPricing.adjustedTarget(state);
    }
    ...
    function sellBaseToken(PMMState memory state, uint256 payBaseAmount) internal pure returns (uint256 receiveQuoteAmount, RState newR) {
        if (state.R == RState.ONE) {
            // case 1: R=1
            // R falls below one
            receiveQuoteAmount = _ROneSellBaseToken(state, payBaseAmount);
            newR = RState.BELOW_ONE;
        } else if (state.R == RState.ABOVE_ONE) {
            uint256 backToOnePayBase = state.B0 - state.B;
            uint256 backToOneReceiveQuote = state.Q - 
            state.Q0;
```
Note that deposits/withdrawals will continue to apply the bad ratio:
```solidity
    } else if (baseReserve > 0 && quoteReserve > 0) {
        // case 2. normal case
        uint256 baseInputRatio = DecimalMath.divFloor(baseInput, baseReserve);
        uint256 quoteInputRatio = DecimalMath.divFloor(quoteInput, quoteReserve);
        uint256 mintRatio = quoteInputRatio < baseInputRatio ? quoteInputRatio : baseInputRatio;
        shares = DecimalMath.mulFloor(totalSupply(), mintRatio);
        _BASE_TARGET_ = (uint256(_BASE_TARGET_) + DecimalMath.mulFloor(uint256(_BASE_TARGET_), mintRatio)).toUint112();
        _QUOTE_TARGET_ = (uint256(_QUOTE_TARGET_) + DecimalMath.mulFloor(uint256(_QUOTE_TARGET_), mintRatio)).toUint112();
```

## Recommendation

Use `DecimalMath.mulCeil()` to protect against the rounding error.

Based on our previous audit, it was discussed that using mulCeil here would not be the right answer since that would just create imprecision in the ratio in the other direction.
 
It would be good if the submitter could provide a PoC showing a veritable exploit case for this one.
 
Acknowledged, but will not fix it on contract level but filtering pool quality and legitimacy on our main frontend.

Hi,
 
The impact demonstrated is doubling the ratio of the pool, which is a core invariant of the MIMswap platform. It means pricing will be incorrect, which is the core functionality of an AMM. A user who will make a trade assuming they will follow the price set out by the I parameter will make _incorrect trades_ , losing their funds inappropriately. I believe the direct risk of loss of funds by innocent traders who are not making a mistake, warrants the severity of High.

  1. The attacker can compromise _QUOTE_TARGET_ in buyShares() after the pool is created.
          
          function createPool(
              address baseToken,
              address quoteToken,
              uint256 lpFeeRate,
              uint256 i,
              uint256 k,
              address to,
              uint256 baseInAmount,
              uint256 quoteInAmount
          ) external returns (address clone, uint256 shares) {
              _validateDecimals(IERC20Metadata(baseToken).decimals(), IERC20Metadata(quoteToken).decimals());
          
              clone = IFactory(factory).create(baseToken, quoteToken, lpFeeRate, i, k);
          
              baseToken.safeTransferFrom(msg.sender, clone, baseInAmount);
              quoteToken.safeTransferFrom(msg.sender, clone, quoteInAmount);
              (shares, , ) = IMagicLP(clone).buyShares(to);  <========
          }
 
   2. The victim calls sellBase, and the call chain is as follows. In adjustedTarget, state.Q0 will not be adjusted since state.R == RState.ONE.
          
          function sellBase(address to) external nonReentrant returns (uint256 receiveQuoteAmount) {
              uint256 baseBalance = _BASE_TOKEN_.balanceOf(address(this));
              uint256 baseInput = baseBalance - uint256(_BASE_RESERVE_);
              uint256 mtFee;
              uint256 newBaseTarget;
              PMMPricing.RState newRState;
              (receiveQuoteAmount, mtFee, newRState, newBaseTarget) = querySellBase(tx.origin, baseInput); <==============
          ...
          function querySellBase(
              address trader,
              uint256 payBaseAmount
          ) public view returns (uint256 receiveQuoteAmount, uint256 mtFee, PMMPricing.RState newRState, uint256 newBaseTarget) {
              PMMPricing.PMMState memory state = getPMMState(); <========
              (receiveQuoteAmount, newRState) = PMMPricing.sellBaseToken(state, payBaseAmount); <======
          ...
          function getPMMState() public view returns (PMMPricing.PMMState memory state) {
              state.i = _I_;
              state.K = _K_;
              state.B = _BASE_RESERVE_;
              state.Q = _QUOTE_RESERVE_;
              state.B0 = _BASE_TARGET_; // will be calculated in adjustedTarget
              state.Q0 = _QUOTE_TARGET_;
              state.R = PMMPricing.RState(_RState_);
              PMMPricing.adjustedTarget(state); <======
          }
          ...
          function adjustedTarget(PMMState memory state) internal pure {
              if (state.R == RState.BELOW_ONE) {
                  state.Q0 = Math._SolveQuadraticFunctionForTarget(state.Q, state.B - state.B0, state.i, state.K);
              } else if (state.R == RState.ABOVE_ONE) {
                  state.B0 = Math._SolveQuadraticFunctionForTarget(
                      state.B,
                      state.Q - state.Q0,
                      DecimalMath.reciprocalFloor(state.i),
                      state.K
                  );
              }
          }
 
   3. sellBaseToken calls _ROneSellBaseToken, and _ROneSellBaseToken calls _SolveQuadraticFunctionForTrade to use compromised _QUOTE_TARGET_ for calculation. It’ll compromise the victim.
          
          function sellBaseToken(PMMState memory state, uint256 payBaseAmount) internal pure returns (uint256 receiveQuoteAmount, RState newR) {
              if (state.R == RState.ONE) {
                  // case 1: R=1
                  // R falls below one
                  receiveQuoteAmount = _ROneSellBaseToken(state, payBaseAmount); <======
                  newR = RState.BELOW_ONE;
          ...
          function _ROneSellBaseToken(
              PMMState memory state,
              uint256 payBaseAmount
          )
              internal
              pure
              returns (
                  uint256 // receiveQuoteToken
              )
          {
              // in theory Q2 <= targetQuoteTokenAmount
              // however when amount is close to 0, precision problems may cause Q2 > targetQuoteTokenAmount
              return Math._SolveQuadraticFunctionForTrade(state.Q0, state.Q0, payBaseAmount, state.i, state.K); <======
          }
```

Therefore, High Severity is warranted.

_Note: For full discussion, see[here](https://github.com/code-423n4/2024-03-abracadabra-money-findings/issues/221)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the initialization logic of MagicLP pools where the ideal reserve ratio, denoted as I, is used to compute the target quote reserve during the first liquidity provision. The contract decides how many shares to mint based on a conditional expression that compares the supplied quote balance with the product of the base balance and I, calculated using a floor‑rounded multiplication (DecimalMath.mulFloor). If the quote balance is deemed insufficient, the shares are derived by dividing the quote balance by I, also using floor division. Because the comparison uses mulFloor, a tiny rounding discrepancy can cause the condition to evaluate incorrectly when the quote balance is extremely small relative to the base balance. In the example where quoteBalance equals 1, baseBalance equals 19999 and I equals 1e14, the floor multiplication yields exactly 1, making the comparison false and causing the contract to select the baseBalance path. Consequently the contract records a BASE_TARGET of 19999 and a QUOTE_TARGET of 1, establishing a reserve ratio of 1:19999 instead of the intended 1:1000. This amplified rounding error breaks the core invariant that the pool’s pricing mechanism assumes, effectively doubling the I ratio used for pricing. An attacker can trigger this state by supplying minimal quote tokens during the initial deposit, either on a freshly created pool or immediately after the factory’s init call. Once the QUOTE_TARGET is corrupted, all subsequent pricing calculations – including sellBase operations that rely on the adjustedTarget function – use the wrong target, leading to severely mispriced trades. Users who trust the advertised I value will receive far less value than expected, often seeing their trades execute at a price that appears to be arbitrarily high or low, resulting in unexpected loss of funds. The issue is subtle because the faulty condition only manifests with extreme rounding cases and small numbers, making it easy to overlook during standard testing. It was discovered during a manual audit of the pool’s initialization code, where the auditor identified the mismatch between mulFloor and the intended safety check. The bug is hard to notice in normal operation because most pools are created with balanced token amounts where the rounding error does not surface. To remediate the problem, the comparison should employ a ceiling‑rounded multiplication (DecimalMath.mulCeil) so that the condition correctly detects insufficient quote balance and forces the division path, preserving the intended I ratio. Alternatively, the logic could be restructured to avoid floor‑based comparisons altogether, ensuring that the target reserves are always derived from a mathematically consistent formula. Fixing this issue restores the invariant that the pool’s pricing follows the declared I parameter, protecting traders from inadvertent loss and maintaining the integrity of the AMM’s core accounting assumptions.
